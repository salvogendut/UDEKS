#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Native xwave candidate: retained-grid oracle, worker leases and WM events.

This uses VICE keyboard/pointer injection, not physical mouse qualification.
The production XCLOCK/XWAVE binaries on the disk remain unchanged.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import time
from add_disk_apps import add_apps
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_worker_probe import expected_surface
from native_clock_probe import clock_commands
from o65_to_udex import relocate_executable
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, receive_prompts, quote_monitor_path, parse_monitor_byte
from xcalc_probe import bitmap_preview, pointer_test_scratch

ROOT=Path(__file__).resolve().parents[1]


def wave_paths(width,height):
    """Independent encoder of all edges in the accepted legacy sinc grid."""
    samples=expected_surface()
    def point(row,col):
        z=samples[row*25+col]; z=z-256 if z>=128 else z
        return (3+(col+20-row)*4*(width-6)//176,
                14+(28+col+row-z)*(height-18)//75)
    strips=[[(r,c) for c in range(25)] for r in range(0,21,2)]
    strips += [[(r,c) for r in range(21)] for c in range(0,25,2)]
    stream=bytearray(); edges=[]
    for strip in strips:
        points=[point(*p) for p in strip]
        x,y=points[0]; stream.extend((len(points)|(128 if x>=256 else 0),x&255,y))
        for (x,y),(xx,yy) in zip(points,points[1:]):
            assert -128<=xx-x<=127 and -128<=yy-y<=127
            stream.extend(((xx-x)&255,(yy-y)&255)); edges.append((x,y,xx,yy))
    stream.append(0); stream.extend(bytes(-len(stream)%8))
    assert len(stream)==1128 and len(edges)==524
    return bytes(stream),edges


def check_console_guard(port,entry,path):
    """Step the installed guard through its return path, then restore CPU/map.

    Stop BEFORE RTS: this does not borrow or change any task's live stack.
    Four instructions prove the post-overlay entry bypasses glyph upload.
    """
    transcript=bytearray()
    with socket.create_connection(('127.0.0.1',port),timeout=3) as connection:
        connection.settimeout(10)
        def run(command,first=False):
            connection.sendall(command.encode()+b'\n')
            reply=receive_prompts(connection,2 if first else 1)
            transcript.extend(command.encode()+b'\n'+reply)
            return reply
        def registers(reply):
            match=re.search(rb'\.;([0-9a-fA-F]{4})\s+([0-9a-fA-F]{2})\s+([0-9a-fA-F]{2})\s+'
                rb'([0-9a-fA-F]{2})\s+([0-9a-fA-F]{2})\s+[0-9a-fA-F]{2}\s+[0-9a-fA-F]{2}\s+([01]{8})',reply)
            if not match: raise ValueError('unexpected VICE register record')
            return [int(value,16) for value in match.groups()[:5]]+[int(match[6],2)]
        live=parse_monitor_byte(run('m ff00 ff00',True),0xff00)
        saved=registers(run('r'))
        try:
            run('> ff01 00')
            run(f'r PC={entry:04x}, A=ff, X=ff, FL=24')
            run('step 4')
            after=registers(run('r'))
            if after[:5]!=[entry+8,0,0,saved[3],saved[4]]:
                raise AssertionError(('console reentry guard',after))
            if parse_monitor_byte(run(f'm {entry+8:04x} {entry+8:04x}'),entry+8)!=0x60:
                raise AssertionError('guard did not stop at RTS')
        finally:
            pc,a,x,y,stack,flags=saved
            run(f'r PC={pc:04x}, A={a:02x}, X={x:02x}, Y={y:02x}, SP={stack:02x}, FL={flags:02x}')
            run(f'> ff00 {live:02x}')
            connection.sendall(b'x\n')
            path.write_bytes(transcript)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--drive',choices=('1541','1571','1581'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); work=args.output.resolve(); work.mkdir(parents=True,exist_ok=True)
    program=(ROOT/'build/native-clients/wave/NWAVE.BIN').read_bytes()
    clock=(ROOT/'build/native-clients/clock/NCLOCK.BIN').read_bytes()
    image=add_apps(args.disk.read_bytes(),[('NWAVE.BIN',program),('NCLOCK.BIN',clock)])
    disk=work/('native-wave'+args.disk.suffix); disk.write_bytes(image)
    text=(ROOT/'build/8502/udeks-8502.map').read_text(); segments=map_segments(text)
    exports=map_exports(text)
    app=map_exports((ROOT/'build/native-clients/wave/xwave_native.map').read_text())
    clk=map_exports((ROOT/'build/native-clients/clock/xclock_native.map').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    scratch=pointer_test_scratch(text)
    assets=(ROOT/'build/assets/udeks-vdc-text.bin').read_bytes()
    port=choose_port(); proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')
    records=[]; patched=[]
    def address(name): return app['_native_wave_'+name][0]-0x1000+0x2300
    def capture(tag,where,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),where,where+size-1,bank)])[0]
    def vdc(tag,where,size):
        path=work/(tag+'.bin'); path.unlink(missing_ok=True)
        with socket.create_connection(('127.0.0.1',port),timeout=3) as connection:
            connection.settimeout(10)
            try:
                connection.sendall(b'bank vdc\n'); receive_prompts(connection,2)
                command=f'save {quote_monitor_path(path)} 0 {where:04x} {where+size-1:04x}\n'
                connection.sendall(command.encode()); reply=receive_prompts(connection)
                if b'Saving' not in reply: raise RuntimeError(reply)
            finally:
                connection.sendall(b'bank cpu\n'); receive_prompts(connection)
                connection.sendall(b'x\n')
        data=path.read_bytes()[2:]
        if len(data)!=size: raise AssertionError('short VDC capture')
        return data
    def wait_task(offset,value,deadline):
        # Lifecycle state is bank-0 RAM; a plain monitor m can sample bank 1.
        while capture('task-state',slots+offset,1)[0]!=value:
            if time.monotonic()>deadline: raise TimeoutError(('task state',offset,value))
            time.sleep(.1)
    def wait_prompt(deadline):
        wait_task(1,4,deadline)
        wait_task(2,2,deadline) # WAITING on READ, not command-completion POLL
    def command(line,contains=''):
        deadline=time.monotonic()+180
        wait_prompt(deadline)
        before=byte(port,0xf3d8); type_command(port,queue,line,deadline)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline)
        wait_prompt(deadline)
        while True:
            data=capture('console',segments['LOWBSS'][0],0x558)
            output='\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
            if contains in output: break
            if time.monotonic()>deadline: raise AssertionError((line,output))
            time.sleep(.1)
        records.append(dict(command=line,console=output)); print('PASS',line,flush=True)
    def counter(tag):
        data=capture(tag,0xf190,32)
        return int.from_bytes(data[12:14],'little')
    def verify(tag,width,height):
        deadline=time.monotonic()+120
        expected,edges=wave_paths(width,height)
        while True:
            sizes=capture(tag+'-size',address('width'),3,'worker')
            rows=capture(tag+'-rows',address('rows'),3,'worker')
            paths=capture(tag+'-paths',address('paths'),1128,'worker')
            retained=capture(tag+'-retained',0xc600,1128,'worker')
            if sizes==width.to_bytes(2,'little')+bytes((height,)) and rows[0]==21 and rows[1] and not rows[2] and paths==retained==expected:
                break
            if time.monotonic()>deadline: raise AssertionError((tag,sizes.hex(),rows.hex(),'path mismatch'))
            time.sleep(.1)
        if capture(tag+'-samples',address('samples'),525,'worker')!=expected_surface():
            raise AssertionError('private sample cache changed')
        code=relocate_executable(program,0x2300,0x1200)[16:]
        if capture(tag+'-code',0x2300,len(code),'worker')!=code: raise AssertionError('app code overwritten')
        records.append(dict(check=tag,width=width,height=height,edges=len(edges),presents=rows[1]))
        print('PASS',tag,flush=True)
        return rows[1]
    def pointer(x,y,buttons):
        if not patched:
            for name,length,offsets in (('x',10,((3,0),(6,1))),('y',4,((1,2),)),('buttons',4,((1,3),))):
                where=exports['_udeks_pointer_'+name][0]; original=capture('pointer-'+name,where,length)
                expected={'x':b'\x08\x78\xad\xd8\xf1\xae\xd9\xf1\x28\x60',
                    'y':b'\xad\xda\xf1\x60','buttons':b'\xad\xdb\xf1\x60'}[name]
                if original!=expected: raise ValueError('pointer getter changed')
                patched.append((where,original)); data=bytearray(original)
                for offset,relative in offsets: data[offset:offset+2]=(scratch+relative).to_bytes(2,'little')
                sp.write_kernel_blocks(port,[(scratch,bytes((12,0,40,0))),(where,data)])
        sp.write_kernel_blocks(port,[(scratch,(x+12).to_bytes(2,'little')+bytes((y+40,buttons)))])
    def release(x,y):
        pointer(x,y,0); sp.wait_for_byte(port,0xf248,0,time.monotonic()+120)
        sp.write_kernel_blocks(port,patched); patched.clear()
    def resize(handle,x,y,w,h,nw,nh):
        pointer(x+w-3,y+h-3,0); sp.wait_for_byte(port,0xf24d,0,time.monotonic()+90)
        pointer(x+w-3,y+h-3,1); sp.wait_for_byte(port,0xf248,handle,time.monotonic()+90)
        pointer(x+nw-1,y+nh-1,1); sp.wait_for_byte(port,0xf24c,nw&255,time.monotonic()+90)
        release(x+nw-1,y+nh-1)
    def canvas(tag):
        deadline=time.monotonic()+120
        while True:
            start,end,_=segments['VICSHADOW']
            shadow,bitmap=sp.capture_blocks(port,[(work/(tag+'-shadow.bin'),start,end,'kernel'),
                (work/(tag+'-bitmap.bin'),0x6000,0x7f3f,'worker')])
            if shadow==bitmap: break
            if time.monotonic()>deadline: raise AssertionError('VIC/shadow mismatch')
            time.sleep(.1)
        (work/(tag+'.png')).write_bytes(bitmap_preview(bitmap))
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        if capture('assets-before',0x96a8,1112)!=assets: raise AssertionError('boot assets mismatch')
        font=byte(port,0xf082)<<8
        if vdc('font-before',font,1008)!=assets[16:1024]: raise AssertionError('custom glyph upload mismatch')
        leases=counter('engine-before')
        command('nwave &')
        sp.wait_for_byte(port,0xf246,1,time.monotonic()+120)
        handle=byte(port,0xf247)
        initial=verify('initial-wave',176,112)
        after=counter('engine-plotted')
        if (after-leases)&65535!=21: raise AssertionError('expected exactly 21 bounded worker leases')
        # Header and tile maps stay live; only already-uploaded glyph data retires.
        after_assets=capture('assets-after',0x96a8,1112)
        if after_assets[:16]!=assets[:16] or after_assets[1024:]!=assets[1024:]:
            raise AssertionError('live logo metadata overwritten')
        if after_assets[16:1024]==assets[16:1024]: raise AssertionError('overlay was not installed')
        if vdc('font-after',font,1008)!=assets[16:1024]: raise AssertionError('VDC glyphs corrupted')
        check_console_guard(port,exports['_udeks_console_start'][0],work/'console-guard.txt')
        canvas('native-wave')
        pointer(38,33,0); sp.wait_for_byte(port,0xf24d,0,time.monotonic()+90)
        pointer(38,33,1); sp.wait_for_byte(port,0xf248,handle,time.monotonic()+90)
        pointer(54,49,1); sp.wait_for_byte(port,0xf249,44,time.monotonic()+90)
        release(54,49)
        if verify('moved-wave',176,112)!=initial: raise AssertionError('move reprojected app geometry')
        if counter('engine-moved')!=after: raise AssertionError('move involved Z80')
        resize(handle,44,44,176,112,256,146)
        # EVENT reports coalesced current geometry, including outline sizes
        # observed while the resize is held. Intermediate sizes are legal.
        if verify('resized-wave',256,146)<=initial: raise AssertionError('resize did not reproject')
        if counter('engine-resized')!=after: raise AssertionError('resize recomputed the height field')
        resize(handle,44,44,256,146,48,48); verify('minimum-wave',48,48)
        resize(handle,44,44,48,48,176,112); verify('restored-wave',176,112)
        command('nclock &'); sp.wait_for_byte(port,0xf246,2,time.monotonic()+90)
        command('date 03:15:00','03:15:00')
        deadline=time.monotonic()+90
        while capture('clock-retained',0xcb00,344,'worker')!=clock_commands(3,15):
            if time.monotonic()>deadline: raise AssertionError('independent clock image mismatch')
            time.sleep(.1)
        verify('after-stacking',176,112)
        if counter('engine-stacked')!=after: raise AssertionError('stacking involved Z80')
        command('cowsay native wave','native wave'); canvas('native-clock-wave')
        command('xclock &'); command('xwave &')
        sp.wait_for_byte(port,0xf246,4,time.monotonic()+90)
        sp.wait_for_byte(port,0xf27a,21,time.monotonic()+150)
        verify('four-apps-wave',176,112); canvas('four-apps')
        command('xinit -q','VIC-II graphics stopped')
        for offset in (17,25): wait_task(offset,0,time.monotonic()+90)
        leases=counter('engine-before-reload')
        command('nwave &'); verify('reloaded-wave',176,112)
        if (counter('engine-reloaded')-leases)&65535!=21: raise AssertionError('reload worker lease count')
        if vdc('font-reloaded',font,1008)!=assets[16:1024]: raise AssertionError('glyphs corrupted on reload')
        command('xinit -q','VIC-II graphics stopped')
        wait_task(17,0,time.monotonic()+90)
        command('echo wave cleanup passed','wave cleanup passed')
        if byte(port,0xf11b): raise AssertionError('task guard failure')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive,
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),
            fixture_sha256=hashlib.sha256(image).hexdigest(),program_sha256=hashlib.sha256(program).hexdigest(),
            edges=524,path_bytes=1128,worker_leases_per_load=21,move_without_present=True,
            resize_without_worker=True,stacking_without_worker=True,retained_oracle=True,
            vdc_glyphs_preserved=True,live_asset_metadata_preserved=True,four_apps=True,
            console_reentry_guard=True,
            reload=True,console_live=True,stack_guards=True,records=records),indent=2)+'\n')
    except Exception:
        capture('failure-common',0xf000,4096)
        capture('failure-kernel',0x2000,0xb000)
        capture('failure-graphics',0xc00,0x600)
        capture('failure-bank1',0x2000,0xe000,'worker')
        raise
    finally:
        sp.terminate(proc,port); os.close(master)


if __name__=='__main__': main()

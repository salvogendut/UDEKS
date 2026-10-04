#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold boot and exercise four independently scheduled disk clients in VICE."""
import argparse
import json
import hashlib
import re
import socket
import os
from pathlib import Path
import time
from add_disk_apps import add_apps
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_app_layout import ALLOCATIONS, RETAINED_BASE, RETAINED_LIMIT
from o65_to_udex import relocate_executable
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, receive_prompts, quote_monitor_path
from xcalc_probe import bitmap_preview, pointer_test_scratch
from native_wave_probe import wave_paths
from native_worker_probe import expected_surface
from native_clock_probe import clock_commands

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--drive',choices=('1541','1571','1581'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); work=args.output.resolve(); work.mkdir(parents=True,exist_ok=True)
    text=(ROOT/'build/8502/udeks-8502.map').read_text()
    exports=map_exports(text); segments=map_segments(text)
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    example=(ROOT/'build/generic-apps/example/HELLO.BIN').read_bytes()
    unknown=('orbit','canvas','hello','fourth','extra')
    bad=bytearray(example); bad[-1]=255
    image=add_apps(args.disk.read_bytes(),[(name.upper()+'.BIN',example) for name in unknown]+[('BADPATCH.BIN',bytes(bad))])
    disk=work/('qualified'+args.disk.suffix); disk.write_bytes(image)
    maps={name:map_exports((ROOT/path).read_text()) for name,path in (
        ('xwave','build/user/native-wave/xwave_native.map'),
        ('xcalc','build/user/native-calc/xcalc_native.map'),
        ('xdraw','build/user/native-draw/xdraw.map'),
        ('hello','build/generic-apps/example/xhello.map'))}
    allocations={task:(base,limit,stack,zp,hp) for task,base,limit,stack,zp,hp in ALLOCATIONS}
    def app_address(name,symbol,task):
        return maps[name][symbol][0]-0x1000+allocations[task][0]
    wm=re.search(r'^window_manager\.o:\n((?:[ \t].*\n)+)',text,re.M)[1]
    click=segments['BSS'][0]+int(re.search(r'BSS\s+Offs=([0-9A-F]+)\s+Size=000004',wm)[1],16)
    scratch=pointer_test_scratch(text)
    port=choose_port(); records=[]; patched=[]
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')
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
    def panel(tag,names):
        sp.wait_for_byte(port,0xf083,31,time.monotonic()+120)
        for row,name in enumerate(('xinit',*(names[t] for t in (3,4,5,6))),2):
            expected=bytes((ord(c.upper())&31 if c.isalpha() else ord(c)) for c in name[:9]).ljust(9,b' ')
            if vdc(tag+'-panel-'+str(row),0x04b2+row*80,9)!=expected:
                raise AssertionError(('panel text',name,row))
            if vdc(tag+'-attr-'+str(row),0x0cb2+row*80,9)!=bytes((128,))*9:
                raise AssertionError('panel attributes')
        records.append(dict(check=tag+'-panel',names=dict(names)))
    def console():
        data=capture('console',segments['LOWBSS'][0],0x558)
        return '\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
    def wait_prompt(deadline):
        while capture('root-state',slots+1,2)!=b'\x04\x02':
            if time.monotonic()>deadline: raise TimeoutError(('root prompt',console()))
            time.sleep(.05)
    def command(line,contains=''):
        deadline=time.monotonic()+180; wait_prompt(deadline)
        before=byte(port,0xf3d8); type_command(port,queue,line,deadline)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline)
        wait_prompt(deadline)
        output=console()
        if contains not in output: raise AssertionError((line,output))
        records.append(dict(command=line,console=output)); print('PASS',line,flush=True)
    def windows(count):
        try: sp.wait_for_byte(port,0xf246,count,time.monotonic()+120)
        except TimeoutError: raise AssertionError((count,console()))
    def peers(tag,names):
        for task,base,limit,stack,zp,hp in ALLOCATIONS:
            if task not in names: continue
            program=example if names[task] in unknown else (ROOT/('build/user/'+names[task]+'.udx')).read_bytes()
            installed=relocate_executable(program,base,limit-base)
            code=installed[16:]
            if names[task] in unknown:
                # HELLO deliberately changes its initialized drawing DATA.
                data=map_segments((ROOT/'build/generic-apps/example/xhello.map').read_text())['DATA'][0]
                code=code[:data-0x1000]
            if capture(tag+'-'+str(task)+'-code',base,len(code),'worker')!=code:
                raise AssertionError(('code changed',task))
            for offset in (0,0xb0):
                if capture(tag+'-'+str(task)+'-guard-'+str(offset),stack+offset,16,'worker')!=b'\xa5'*16:
                    raise AssertionError(('software stack guard',task,offset))
        lengths=capture(tag+'-lengths',exports['_udeks_retained_lengths'][0],8)
        total=sum(int.from_bytes(lengths[n:n+2],'little')&0x7fff for n in range(0,8,2))
        if total>RETAINED_LIMIT-RETAINED_BASE: raise AssertionError('retained pool overflow')
        capture(tag+'-pool',RETAINED_BASE,RETAINED_LIMIT-RETAINED_BASE)
        records.append(dict(check=tag,retained_bytes=total,live=dict(names)))
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

    def retained(task,tag):
        lengths=capture(tag+'-lengths',exports['_udeks_retained_lengths'][0],8)
        sizes=[int.from_bytes(lengths[i:i+2],'little')&0x7fff for i in range(0,8,2)]
        length=sizes[task-3]
        return capture(tag+'-retained',RETAINED_BASE+sum(sizes[:task-3]),length) if length else b''
    def leases(tag):
        return int.from_bytes(capture(tag,0xf19c,2),'little')
    def wave(tag,width,height):
        deadline=time.monotonic()+120
        expected=wave_paths(width,height)[0]
        while True:
            state=capture(tag+'-state',app_address('xwave','_native_wave_rows',5),3,'worker')
            dimensions=capture(tag+'-size',app_address('xwave','_native_wave_width',5),3,'worker')
            if (state[0]==21 and state[1] and not state[2] and
                    dimensions==width.to_bytes(2,'little')+bytes((height,)) and retained(5,tag)==expected):
                break
            if time.monotonic()>deadline: raise AssertionError(('wave retained grid',tag))
            time.sleep(.1)
        if capture(tag+'-samples',app_address('xwave','_native_wave_samples',5),525,'worker')!=expected_surface():
            raise AssertionError('wave height field')
        count=capture(tag+'-presents',app_address('xwave','_native_wave_presents',5),1,'worker')[0]
        records.append(dict(check=tag,edges=524,presents=count))
        print('PASS',tag,flush=True); return count
    def resize_wave(handle,x,y,width,height,nw,nh):
        before=wave('before-resize',width,height); count=leases('leases-before-resize')
        pointer(x+width-3,y+height-3,0)
        sp.wait_for_byte(port,0xf24d,0,time.monotonic()+90)
        pointer(x+width-3,y+height-3,1)
        sp.wait_for_byte(port,0xf248,handle,time.monotonic()+90)
        pointer(x+nw-1,y+nh-1,1)
        sp.wait_for_byte(port,0xf24c,nw&255,time.monotonic()+90)
        time.sleep(.5)
        if capture('held-presents',app_address('xwave','_native_wave_presents',5),1,'worker')[0]!=before:
            raise AssertionError('wave published during outline resize')
        release(x+nw-1,y+nh-1)
        if wave('resized-wave',nw,nh)!=before+1 or leases('leases-resized')!=count:
            raise AssertionError('resize repeated projection or worker computation')
    def injected_click(handle,x,y):
        sp.write_kernel_blocks(port,[(click,bytes((handle,x&255,x>>8,y)))])
    def wait_value(tag,address,expected):
        deadline=time.monotonic()+90
        while capture(tag,address,len(expected),'worker')!=expected:
            if time.monotonic()>deadline: raise AssertionError((tag,expected))
            time.sleep(.1)
    def wait_free(task):
        deadline=time.monotonic()+90
        while capture('task-free',slots+(task-1)*8+1,1)!=b'\0':
            if time.monotonic()>deadline: raise AssertionError(('not reaped',task))
            time.sleep(.1)
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        count=leases('leases-boot')
        command('xclock &'); windows(1)
        command('xwave &'); windows(2)
        wave_handle=byte(port,0xf247)
        initial=wave('initial-wave',176,112)
        if (leases('leases-initial')-count)&65535!=21: raise AssertionError('worker leases per load')
        pointer(38,33,0);sp.wait_for_byte(port,0xf24d,0,time.monotonic()+90)
        pointer(38,33,1);sp.wait_for_byte(port,0xf248,wave_handle,time.monotonic()+90)
        pointer(54,49,1);sp.wait_for_byte(port,0xf249,44,time.monotonic()+90)
        release(54,49)
        if wave('moved-wave',176,112)!=initial: raise AssertionError('move reprojected')
        resize_wave(wave_handle,44,44,176,112,256,146)
        resize_wave(wave_handle,44,44,256,146,176,112)
        if (leases('leases-after-resizes')-count)&65535!=21: raise AssertionError('move/resize worker lease')
        command('xcalc &');windows(3)
        calc_handle=byte(port,0xf247)
        for key in '12+34=':
            i='789/456*123-C0=+.N  '.index(key)
            injected_click(calc_handle,11+(i%4)*25,40+(i//4)*20);time.sleep(.3)
        wait_value('calc-46',app_address('xcalc','_udeks_calc_value',3),(4600).to_bytes(4,'little'))
        command('xdraw &');windows(4)
        draw_handle=byte(port,0xf247)
        injected_click(draw_handle,10,25)
        wait_value('draw-cell',app_address('xdraw','_udeks_xdraw_cells',6),bytes((1,))+bytes(23))
        peers('four',{4:'xclock',5:'xwave',3:'xcalc',6:'xdraw'})
        panel('four',{4:'xclock',5:'xwave',3:'xcalc',6:'xdraw'})
        command('date 03:15:00','03:15:00')
        deadline=time.monotonic()+90
        while retained(4,'clock')!=clock_commands(3,15):
            if time.monotonic()>deadline: raise AssertionError('clock commands')
            time.sleep(.1)
        command('cowsay four native','four native')
        command('ls /bin','badpatch') # last entry; early rows may have scrolled out
        peers('after-console',{4:'xclock',5:'xwave',3:'xcalc',6:'xdraw'})
        canvas('four-defaults')
        command('xclock &','slot busy'); windows(4)
        command('xwave -q'); windows(3);wait_free(5)
        command('xwave &'); windows(4);wave('reloaded-wave',176,112)
        peers('reloaded',{4:'xclock',5:'xwave',3:'xcalc',6:'xdraw'})
        command('xinit -q'); windows(0)
        for task in allocations: wait_free(task)
        # Same independently linked, OS-unknown executable in every allocation.
        live={}
        for name,task in zip(unknown,(6,4,5,3)):
            command(name+' &'); windows(len(live)+1);live[task]=name
            handle=byte(port,0xf247)
            injected_click(handle,20,28)
            wait_value(name+'-click',app_address('hello','_hello_clicks',task),bytes((1,)))
            if task!=6:
                wait_value('peer-click',app_address('hello','_hello_clicks',6),bytes((1,)))
        names=capture('unknown-names',exports['_udeks_banked_graphics_names'][0],64)
        for task,name in live.items():
            if names[(task-3)*16:(task-2)*16]!=name.encode().ljust(16,bytes(1)):
                raise AssertionError('running names differ')
        peers('unknown-four',live)
        panel('unknown-four',live)
        command('extra &','slot busy');windows(4)
        command('canvas -q');windows(3);wait_free(4)
        before={task:retained(task,'before-bad-'+str(task)) for task in (3,5,6)}
        command('badpatch &','loader error');windows(3)
        for task,data in before.items():
            if retained(task,'after-bad-'+str(task))!=data: raise AssertionError('rejection damaged peer')
        command('extra &');windows(4);live[4]='extra'
        wait_value('reuse-cleared-bss',app_address('hello','_hello_clicks',4),bytes(1))
        peers('unknown-reused',live)
        panel('unknown-reused',live)
        canvas('unknown-four')
        command('xinit -q'); windows(0)
        for task in allocations: wait_free(task)
        command('echo four-slot cleanup passed','four-slot cleanup passed')
        if byte(port,0xf11b): raise AssertionError('task canary failure')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive,disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256(image).hexdigest(),checks=records),indent=2)+'\n')
    finally:
        sp.terminate(proc,port)
        if master is not None: os.close(master)

if __name__=='__main__': main()

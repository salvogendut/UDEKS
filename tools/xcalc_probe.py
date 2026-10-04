#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""VICE true-drive xcalc load/slot/console test; clicks injected at the WM queue.

This complements, not replaces, the native 1351 input test in 1986.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import time
import zlib
from boot_staging_map import segment_bounds
from gen_capability_imports import map_exports
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, monitor_command

ROOT=Path(__file__).resolve().parents[1]

def pointer_test_scratch(kernel_map):
    """Use only linker-proven helper padding, never task or runtime state."""
    scratch=segment_bounds(kernel_map,'GRAPHICSHELP')[1]+1
    if scratch+4>segment_bounds(kernel_map,'VICSHADOW')[0]:
        raise ValueError('no free pointer-test record; do not overwrite live memory')
    return scratch

def bitmap_preview(bitmap):
    """Render a captured VIC hires bitmap, without the hardware sprite."""
    if len(bitmap)!=8000: raise ValueError('expected full VIC bitmap')
    rows=bytearray()
    for y in range(200):
        rows.append(0)  # PNG unfiltered scanline
        for x in range(320):
            ink=bitmap[(y//8)*320+(x//8)*8+y%8] & (128>>(x%8))
            rows.extend(b'\0\0\0' if ink else b'\xff\xff\0')
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',320,200,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive',choices=('1541','1571'),default='1541')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--four-apps',action='store_true',help='also qualify task-4 xdraw and full capacity')
    args=parser.parse_args()
    work=args.output.resolve();work.mkdir(parents=True,exist_ok=True)
    disk_image=args.disk.read_bytes()
    disk=work/('test'+args.disk.suffix)
    disk.write_bytes(disk_image)
    kernel_map=(ROOT/'build/8502/udeks-8502.map').read_text()
    calc_map=map_exports((ROOT/'build/user/xcalc.map').read_text())
    console_base=segment_bounds(kernel_map,'LOWBSS')[0]
    queue=keyboard_queue_address(kernel_map,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    module=re.search(r'^window_manager\.o:\n((?:[ \t].*\n)+)',kernel_map,re.M)[1]
    offset=int(re.search(r'BSS\s+Offs=([0-9A-F]+)\s+Size=000004',module)[1],16)
    assembly=(ROOT/'build/8502/window_manager.s').read_text()
    if not re.search(r'_click_handle:\s+\.res\s+1,\$00\s+_pending_click:\s+\.res\s+3,\$00',assembly):
        raise ValueError('click queue layout changed')
    click_base=segment_bounds(kernel_map,'BSS')[0]+offset
    value_base=calc_map['_udeks_calc_value'][0]
    port=choose_port()
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),
        log_path=work/'vice.log')
    records=[]
    program=(ROOT/'build/user/xcalc.udx').read_bytes()
    native=program[7]==0
    app_bank='worker' if native else 'kernel'
    app_base=int.from_bytes(program[8:10],'little')
    exports=map_exports(kernel_map)
    pointer_original=[]
    def capture(name,lo,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(name+'.bin'),lo,lo+size-1,bank)])[0]
    def console():
        cells=capture('console',console_base,0x558)
        return '\n'.join(cells[i:i+64].decode('ascii',errors='replace').rstrip()
                         for i in range(0,21*65,65))
    def canvas(name):
        # A shell reply does not fence the compositor's pending bitmap flush.
        # Poll for completed presentation; a persistent mismatch still fails.
        deadline=time.monotonic()+30
        while True:
            shadow,bitmap=sp.capture_blocks(port,[
                (work/(name+'-shadow.bin'),0xa1e0,0xc11f,'kernel'),
                (work/(name+'-bitmap.bin'),0x6000,0x7f3f,'worker')])
            if shadow==bitmap:break
            if time.monotonic()>deadline:raise AssertionError(name+': shadow/VIC bitmap mismatch')
            time.sleep(.2)
        (work/(name+'.png')).write_bytes(bitmap_preview(bitmap))
    def pointer(x,y,buttons):
        # Redirect only the getter operands to a map-proven four-byte test
        # record. Instructions/lengths stay intact, even if paused inside one.
        # This exercises the real WM drag/close path, not a physical 1351.
        scratch=pointer_test_scratch(kernel_map)
        if not pointer_original:
            for name,length,offsets in (('x',10,((3,0),(6,1))),
                ('y',4,((1,2),)),('buttons',4,((1,3),))):
                address=exports['_udeks_pointer_'+name][0]
                original=capture('pointer-'+name,address,length)
                expected={'x':b'\x08\x78\xad\xd8\xf1\xae\xd9\xf1\x28\x60',
                    'y':b'\xad\xda\xf1\x60','buttons':b'\xad\xdb\xf1\x60'}[name]
                if original!=expected: raise ValueError('pointer getter layout changed')
                pointer_original.append((address,original))
                patched=bytearray(original)
                for offset,relative in offsets:
                    patched[offset:offset+2]=(scratch+relative).to_bytes(2,'little')
                sp.write_kernel_blocks(port,[(scratch,bytes((12,0,40,0))),
                    (address,patched)])
        sp.write_kernel_blocks(port,[(scratch,(x+12).to_bytes(2,'little')+bytes((y+40,buttons)))])
    def restore_pointer():
        if pointer_original:
            sp.write_kernel_blocks(port,pointer_original)
            pointer_original.clear()
    def command(text,expected,result=0):
        deadline=time.monotonic()+150
        sp.wait_for_byte(port,slots+1,4,deadline)
        before=byte(port,0xf3d8)
        target={'xclock':2,'xwave':3,'xcalc':5,'xdraw':6}.get(text.split()[0])
        control_before=byte(port,0xf17e) if target else None
        type_command(port,queue,text,deadline)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline)
        if target: sp.wait_for_byte(port,0xf17e,(control_before+1)&255,deadline)
        # Foreground jobs use the compatibility WAIT poll, not blocking READ.
        if text not in ('xclock','xwave','xcalc','xdraw'):
            sp.wait_for_byte(port,slots+1,4,deadline)
        if target:
            reply=capture('reply',0xf3a1,4)
            if reply!=bytes((target,int('-q' in text),int('&' in text),result)):
                raise AssertionError((text,'unexpected completion',reply.hex()))
        # The blocked caller can precede control completion by one poll.
        while time.monotonic()<deadline:
            output=console()
            if expected in output: break
            time.sleep(.1)
        else: raise AssertionError(text+'\n'+output)
        records.append(dict(command=text,console=output))
        print('PASS',text,flush=True)
    def windows(count,mask=None):
        sp.wait_for_byte(port,0xf246,count,time.monotonic()+90)
        if mask is not None: sp.wait_for_byte(port,0xf083,mask,time.monotonic()+90)
    def draw_click(handle,x,y):
        sp.write_kernel_blocks(port,[(click_base,bytes((handle,x,0,y)))])
        sp.wait_for_byte(port,click_base,0,time.monotonic()+30)
        command('echo drawing','drawing')
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        if native:
            command('xclock &','xclock started &')
            if args.four_apps:
                handle=byte(port,0xf247)
                pointer(134,66,0);sp.wait_for_byte(port,0xf24d,0,time.monotonic()+60)
                pointer(134,66,1);sp.wait_for_byte(port,0xf248,handle,time.monotonic()+60)
                pointer(22,17,1);sp.wait_for_byte(port,0xf249,12,time.monotonic()+60)
                pointer(22,17,0);sp.wait_for_byte(port,0xf248,0,time.monotonic()+60)
                restore_pointer()
            command('xwave &','xwave started &')
            sp.wait_for_byte(port,0xf27a,21,time.monotonic()+90)
        command('xcalc &','xcalc started &')
        if native: sp.wait_for_byte(port,0xf246,3,time.monotonic()+60)
        if capture('loaded',app_base,len(program)-16,app_bank)!=program[16:]:
            raise AssertionError('calculator code differs from disk image')
        for keys,expected in [('1.25+2.75=',400),('C7.5/2.5=',300),('C5+N.25=',475)]:
            for key in keys:
                index="789/456*123-C0=+.N  ".index(key)
                x,y=14+(index%4)*25,41+(index//4)*20
                handle=byte(port,0xf247)
                sp.write_kernel_blocks(port,[(click_base,bytes((handle,x,0,y)))])
                deadline=time.monotonic()+15
                while capture('queue',click_base,1)!=b'\0':
                    if time.monotonic()>deadline: raise AssertionError('click not consumed')
                    time.sleep(.05)
                # Wait for application poll to return before injecting again.
                command('echo clicked','clicked')
            value=int.from_bytes(capture('value',value_base,4,app_bank),'little',signed=True)
            if value!=expected: raise AssertionError((keys,value,expected))
            records.append(dict(expression=keys,hundredths=value))
            print('PASS arithmetic',keys,value,flush=True)
        if not native:
            command('xclock &','xclock: slot busy',4)
            command('xwave &','xwave started &')
            sp.wait_for_byte(port,0xf27a,21,time.monotonic()+90)
        command('cowsay calculator','calculator')
        if args.four_apps:
            if not native: raise ValueError('four-app qualification requires banked calculator')
            draw=(ROOT/'build/user/xdraw.udx').read_bytes()
            cells=map_exports((ROOT/'build/user/xdraw.map').read_text())['_udeks_xdraw_cells'][0]
            command('xdraw &','xdraw started &');windows(4,31)
            handle=byte(port,0xf247)
            if capture('draw-loaded',0x3500,len(draw)-16,'worker')!=draw[16:]:
                raise AssertionError('fourth executable differs from disk')
            for index in (0,7,23): draw_click(handle,10+(index%6)*16,24+(index//6)*16)
            expected=bytes(int(i in (0,7,23)) for i in range(24))
            if capture('draw-cells',cells,24,'worker')!=expected:
                raise AssertionError('independent drawing state not updated')
            before=capture('four-retained-before-rejection',0xc600,2560,'worker')
            command('xdraw &','xdraw: slot busy',4)
            command('xcalc &','xcalc: slot busy',4)
            windows(4,31)
            if capture('four-retained-after-rejection',0xc600,2560,'worker')!=before:
                raise AssertionError('capacity rejection changed a live retained image')
            command('free','CPU RAM:');command('cowsay four alive','four alive')
            canvas('four-apps')
            monitor_command(port,f'screenshot "{work/"four-apps-console.bmp"}" 0')
            pointer(226,70,0);sp.wait_for_byte(port,0xf24d,0,time.monotonic()+60)
            pointer(226,70,1);sp.wait_for_byte(port,0xf248,handle,time.monotonic()+60)
            pointer(30,90,1);sp.wait_for_byte(port,0xf249,20,time.monotonic()+60)
            pointer(30,90,0);sp.wait_for_byte(port,0xf248,0,time.monotonic()+60)
            command('echo draw moved','draw moved')
            if capture('draw-cells-after-drag',cells,24,'worker')!=expected:
                raise AssertionError('drag changed drawing state')
            if capture('four-retained-after-drag',0xc600,2560,'worker')!=before:
                raise AssertionError('drag changed retained commands')
            canvas('four-dragged')
            pointer(112,91,1);windows(3,15)
            pointer(112,91,0);restore_pointer()
            command('echo draw closed','draw closed')
            command('xdraw &','xdraw started &');windows(4,31)
            if any(capture('draw-cells-reloaded',cells,24,'worker')):
                raise AssertionError('reload failed to reset private state')
            draw_click(byte(port,0xf247),10,24)
            draw_click(byte(port,0xf247),14,92)
            if any(capture('draw-cells-cleared',cells,24,'worker')):
                raise AssertionError('drawing clear button failed')
            for app,mask in (('xclock',29),('xwave',27),('xcalc',23)):
                command(app+' -q',app+' stopped');windows(3,mask)
                command(app+' &',app+' started &');windows(4,31)
                if app=='xwave':sp.wait_for_byte(port,0xf27a,21,time.monotonic()+90)
            # Restore the value used by the following calculator regression.
            for key in 'C5+N.25=':
                index='789/456*123-C0=+.N  '.index(key)
                draw_click(byte(port,0xf247),14+(index%4)*25,41+(index//4)*20)
            command('xdraw -q','xdraw stopped');windows(3,15)
            command('xdraw','xdraw running (Ctrl+C stops)');windows(4,31)
            sp.write_kernel_blocks(port,[(queue,bytes((1,0xff,3,2))),(queue+64,bytes((1,0,1)))])
            windows(3,15);command('echo draw interrupted','draw interrupted')
            for address in (0x8d00,0x8fb0):
                if capture('draw-guard-'+hex(address),address,16,'worker')!=b'\xa5'*16:
                    raise AssertionError('drawing stack guard changed')
            records.append(dict(four_apps=True,independent_drawing=True,capacity_rejection=True,
                each_app_reloaded=True,draw_close_and_reload=True,draw_ctrl_c_preserves_three=True))
        if native:
            command('free','CPU RAM:')
            handle=byte(port,0xf247)
            retained=capture('retained-before-drag',0xc600,1280,'worker')
            pointer(113,35,0)
            sp.wait_for_byte(port,0xf24d,0,time.monotonic()+60)
            pointer(113,35,1)
            sp.wait_for_byte(port,0xf248,handle,time.monotonic()+60)
            pointer(45,45,1)
            sp.wait_for_byte(port,0xf249,40,time.monotonic()+60)
            pointer(45,45,0)
            sp.wait_for_byte(port,0xf248,0,time.monotonic()+60)
            command('echo dragged','dragged')
            if capture('retained-after-drag',0xc600,1280,'worker')!=retained:
                raise AssertionError('drag changed the committed command image')
            if int.from_bytes(capture('value-after-drag',value_base,4,app_bank),'little',signed=True)!=475:
                raise AssertionError('drag changed calculator state')
            canvas('three-apps')
            pointer(136,46,1)  # close box of the moved 104-wide calculator
            sp.wait_for_byte(port,0xf246,2,time.monotonic()+90)
            pointer(136,46,0)
            restore_pointer()
            command('echo closed','closed')
            command('xcalc &','xcalc started &')
            sp.wait_for_byte(port,0xf246,3,time.monotonic()+60)
            records.append(dict(drag_retains_image=True,close_and_reload=True,peer_windows=2))
            print('PASS drag/close/reload with two peers',flush=True)
        command('xwave -q','xwave stopped')
        command('xcalc -q','xcalc stopped')
        if native: command('xclock -q','xclock stopped')
        command('xclock &','xclock started &')
        if native: command('xcalc &','xcalc started &')
        else: command('xcalc &','xcalc: slot busy',4)
        command('xclock -q','xclock stopped')
        if native: command('xcalc -q','xcalc stopped')
        command('xcalc &','xcalc started &')
        command('echo console still alive','console still alive')
        canvas('bitmap')
        if native:
            command('xcalc -q','xcalc stopped')
            command('xclock &','xclock started &')
            command('xwave &','xwave started &')
            sp.wait_for_byte(port,0xf27a,21,time.monotonic()+90)
            command('xcalc','xcalc running (Ctrl+C stops)')
            sp.wait_for_byte(port,0xf246,3,time.monotonic()+60)
            sp.write_kernel_blocks(port,[(queue,bytes((1,0xff,3,2))),
                (queue+64,bytes((1,0,1)))])
            sp.wait_for_byte(port,0xf246,2,time.monotonic()+60)
            command('echo cancelled','cancelled')
            records.append(dict(foreground_ctrl_c=True,peer_windows=2))
            command('xcalc &','xcalc started &')
            sp.wait_for_byte(port,0xf246,3,time.monotonic()+60)
            if args.four_apps:
                command('xdraw &','xdraw started &');windows(4,31)
            command('xinit -q','VIC-II graphics stopped')
            sp.wait_for_byte(port,0xf246,0,time.monotonic()+60)
            for name,address in (('guard-low',0x8a00),('guard-high',0x8cb0)):
                if capture(name,address,16,'worker')!=b'\xa5'*16:
                    raise AssertionError('calculator software stack guard changed')
            records.append(dict(desktop_closes_all=True,software_guards_ok=True))
        if byte(port,0xf11b): raise AssertionError('lifecycle canary failure')
        monitor_command(port,f'screenshot "{work/"console.bmp"}" 0')
        (work/'result.json').write_text(json.dumps(dict(
            disk_sha256=hashlib.sha256(disk_image).hexdigest(),
            drive=args.drive,native_banked=native,four_apps=args.four_apps,
            click_method='injected WM queue/getters; not native input qualification',
            image_matches_disk=True,shadow_matches_bitmap=True,records=records),indent=2)+'\n')
    except Exception:
        print(monitor_command(port,'r').decode(errors='replace'),flush=True)
        for name,lo,size,bank in (('failure-request',0xf359,38,'kernel'),
            ('failure-slots',slots,64,'kernel'),('failure-module',0xc00,0x600,'kernel'),
            ('failure-bss',segment_bounds(kernel_map,'BSS')[0],128,'kernel'),
            ('failure-native',app_base,0x1200,app_bank)):
            capture(name,lo,size,bank)
        raise
    finally:
        sp.terminate(proc,port);os.close(master)

if __name__=='__main__':main()

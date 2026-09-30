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
        ('-drive8truedrive','-drive8type',args.drive))
    records=[]
    def capture(name,lo,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(name+'.bin'),lo,lo+size-1,bank)])[0]
    def console():
        cells=capture('console',console_base,0x558)
        return '\n'.join(cells[i:i+64].decode('ascii',errors='replace').rstrip()
                         for i in range(0,21*65,65))
    def command(text,expected,result=0):
        deadline=time.monotonic()+150
        sp.wait_for_byte(port,slots+1,4,deadline)
        before=byte(port,0xf3d8)
        target={'xclock':2,'xwave':3,'xcalc':5}.get(text.split()[0])
        control_before=byte(port,0xf17e) if target else None
        type_command(port,queue,text,deadline)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline)
        if target: sp.wait_for_byte(port,0xf17e,(control_before+1)&255,deadline)
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
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        command('xcalc &','xcalc started &')
        program=(ROOT/'build/user/xcalc.udx').read_bytes()
        if capture('loaded',0x0200,len(program)-16)!=program[16:]:
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
            value=int.from_bytes(capture('value',value_base,4),'little',signed=True)
            if value!=expected: raise AssertionError((keys,value,expected))
            records.append(dict(expression=keys,hundredths=value))
            print('PASS arithmetic',keys,value,flush=True)
        command('xclock &','xclock: slot busy',4)
        command('xwave &','xwave started &')
        sp.wait_for_byte(port,0xf27a,21,time.monotonic()+90)
        command('cowsay calculator','calculator')
        command('xwave -q','xwave stopped')
        command('xcalc -q','xcalc stopped')
        command('xclock &','xclock started &')
        command('xcalc &','xcalc: slot busy',4)
        command('xclock -q','xclock stopped')
        command('xcalc &','xcalc started &')
        command('echo console still alive','console still alive')
        shadow=capture('shadow',0xa1e0,8000)
        bitmap=capture('bitmap',0x6000,8000,'worker')
        if shadow!=bitmap: raise AssertionError('shadow/VIC bitmap mismatch')
        (work/'bitmap.png').write_bytes(bitmap_preview(bitmap))
        if byte(port,0xf11b): raise AssertionError('lifecycle canary failure')
        monitor_command(port,f'screenshot "{work/"console.bmp"}" 0')
        (work/'result.json').write_text(json.dumps(dict(
            disk_sha256=hashlib.sha256(disk_image).hexdigest(),
            drive=args.drive,click_method='injected WM queue; native input covered in 1986',
            image_matches_disk=True,shadow_matches_bitmap=True,records=records),indent=2)+'\n')
    finally:
        sp.terminate(proc,port);os.close(master)

if __name__=='__main__':main()

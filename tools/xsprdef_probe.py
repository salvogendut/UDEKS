#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold boot XSPRDEF; check actual VIC pixels, session save and coexistence.

Click delivery uses the compositor queue (as in four_native_probe). The dense
pattern is injected into the app's own edit buffer, then published by a real
click. This does not claim to test the physical mouse or keyboard drivers.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time

from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_app_layout import ALLOCATIONS
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port
from xcalc_probe import bitmap_preview

ROOT = Path(__file__).resolve().parents[1]


def sprite_matches(bitmap, sprite, origin=(4,4)):
    """Every pixel in both panes, not merely the retained command list."""
    for ox,oy,scale in ((8,20,8),(208,20,1)):
        for sy in range(21):
            for sx in range(24):
                expected=bool(sprite[sy*3+sx//8] & (128>>(sx%8)))
                for dy in range(scale):
                    y=origin[1]+oy+sy*scale+dy
                    for dx in range(scale):
                        x=origin[0]+ox+sx*scale+dx
                        actual=bool(bitmap[(y//8)*320+(x//8)*8+y%8] & (128>>(x%8)))
                        if actual != expected: return False
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive',choices=('1541','1571','1581'),default='1541')
    parser.add_argument('--output',type=Path,default=ROOT/'build/xsprdef-probe')
    args=parser.parse_args();work=args.output.resolve();work.mkdir(parents=True,exist_ok=True)
    text=(ROOT/'build/8502/udeks-8502.map').read_text()
    exports=map_exports(text);segments=map_segments(text)
    app=map_exports((ROOT/'build/user/native-xsprdef/xsprdef.map').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    wm=re.search(r'^window_manager\.o:\n((?:[ \t].*\n)+)',text,re.M)[1]
    click=segments['BSS'][0]+int(re.search(r'BSS\s+Offs=([0-9A-F]+)\s+Size=000004',wm)[1],16)
    asm=(ROOT/'build/8502/window_manager.s').read_text()
    if not re.search(r'_click_handle:\s+\.res\s+1,\$00\s+_pending_click:\s+\.res\s+3,\$00',asm):
        raise ValueError('click queue layout changed')
    port=choose_port();checks=[]
    proc,master=sp.launch_vice(args.disk.resolve(),port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')

    def capture(tag,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),address,address+size-1,bank)])[0]

    def command(line,contains=''):
        deadline=time.monotonic()+180
        def prompt():
            while capture('root-state',slots+1,2)!=b'\x04\x02':
                if time.monotonic()>deadline: raise TimeoutError(('prompt',line))
                time.sleep(.05)
        prompt();before=byte(port,0xf3d8)
        type_command(port,queue,line,deadline)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline);prompt()
        data=capture('console',segments['LOWBSS'][0],0x558)
        if contains.encode() not in data: raise AssertionError((line,data))
        checks.append(dict(command=line));print('PASS',line,flush=True)

    def click_at(x,y):
        sp.write_kernel_blocks(port,[(click,bytes((handle,x,0,y)))])
        deadline=time.monotonic()+90
        while capture('click',click,1)!=b'\0':
            if time.monotonic()>deadline: raise TimeoutError('editor did not consume click')
            time.sleep(.05)

    def screen(tag,sprite=None):
        deadline=time.monotonic()+90
        while True:
            start,end,_=segments['VICSHADOW']
            shadow,bitmap=sp.capture_blocks(port,[(work/(tag+'-shadow.bin'),start,end,'kernel'),
                (work/(tag+'-bitmap.bin'),0x6000,0x7f3f,'worker')])
            if shadow==bitmap and (sprite is None or sprite_matches(bitmap,sprite)): break
            if time.monotonic()>deadline: raise AssertionError(('screen mismatch',tag))
            time.sleep(.1)
        (work/(tag+'.png')).write_bytes(bitmap_preview(bitmap))
        checks.append(dict(screen=tag,exact_sprite=sprite is not None))
        print('PASS',tag,flush=True)

    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        command('xsprdef &');sp.wait_for_byte(port,0xf246,1,time.monotonic()+120)
        handle=byte(port,0xf247)
        selected=capture('selected',exports['_udeks_banked_graphics_selected'][0],1)[0]
        task,base,limit,stack,_,_=ALLOCATIONS[selected]
        edit=app['_udeks_xsprdef_pixels'][0]-0x1000+base
        # The formerly dead bottom-right edge of button eight.
        click_at(231,99);screen('blank',bytes(63))
        pattern=bytearray(0xaa if row%2==0 else 0x55 for row in range(21) for _ in range(3))
        sp.write_blocks(port,[(edit,pattern)],'worker')
        click_at(199,187);pattern[62]^=1
        screen('checkerboard',pattern)
        click_at(231,76);screen('save-confirmation',pattern)
        click_at(231,102);screen('cancel-confirmation',pattern)
        click_at(208,52);screen('confirm-again',pattern)
        click_at(208,52);screen('saved-list')
        click_at(231,99);screen('saved-reopened',pattern)
        click_at(231,154);screen('inverted',bytes(b^255 for b in pattern))
        click_at(231,128);screen('cleared',bytes(63))
        click_at(208,78);screen('discarded-list')
        click_at(231,99);screen('discard-reopened',pattern)
        command('xclock &');sp.wait_for_byte(port,0xf246,2,time.monotonic()+120)
        command('xcalc &');sp.wait_for_byte(port,0xf246,3,time.monotonic()+120)
        command('xdraw &');sp.wait_for_byte(port,0xf246,4,time.monotonic()+120)
        command('cowsay sprite test','sprite test');screen('four-apps')
        for task,base,limit,stack,_,_ in ALLOCATIONS:
            for offset in (0,0xb0):
                if capture(f'guard-{task}-{offset}',stack+offset,16,'worker')!=b'\xa5'*16:
                    raise AssertionError(('stack guard',task,offset))
        command('xinit -q');sp.wait_for_byte(port,0xf246,0,time.monotonic()+120)
        command('echo editor cleanup passed','editor cleanup passed')
        if byte(port,0xf11b): raise AssertionError('task canary failure')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive,
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),checks=checks),indent=2)+'\n')
    finally:
        sp.terminate(proc,port)
        if master is not None: os.close(master)


if __name__=='__main__': main()

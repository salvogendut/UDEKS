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
from native_app_layout import ALLOCATIONS, JOINED_ALLOCATION
from storage_shell_probe import sp, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port
from xcalc_probe import bitmap_preview, pointer_test_scratch

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
    global ROOT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT,help='built worktree (also permits baseline comparison)')
    parser.add_argument('--expect-delta',action='store_true',help='require pixel clicks to avoid full composition')
    parser.add_argument('--disk',type=Path,default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive',choices=('1541','1571','1581'),default='1541')
    parser.add_argument('--output',type=Path,default=ROOT/'build/xsprdef-probe')
    args=parser.parse_args();work=args.output.resolve();work.mkdir(parents=True,exist_ok=True)
    ROOT=args.root.resolve()
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
    port=choose_port();checks=[];origin=[4,4];patched=[]
    scratch=pointer_test_scratch(text)
    proc,master=sp.launch_vice(args.disk.resolve(),port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')

    def capture(tag,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),address,address+size-1,bank)])[0]

    def byte(address):
        # Even upper common RAM is hidden by ROM during KERNAL I/O. A plain
        # monitor read of $F3D8 can report opcode $E0 as the command counter.
        return capture('status-'+format(address,'04x'),address,1)[0]

    def wait_byte(address,value,deadline):
        while True:
            try:
                if byte(address)==value: return
            except ConnectionRefusedError:
                if proc.poll() is not None: raise
            if time.monotonic()>deadline:
                raise TimeoutError(f'kernel ${address:04X} never reached ${value:02X}')
            time.sleep(.05)

    def command(line,contains=''):
        deadline=time.monotonic()+180
        def prompt():
            while capture('root-state',slots+1,2)!=b'\x04\x02':
                if time.monotonic()>deadline: raise TimeoutError(('prompt',line))
                time.sleep(.05)
        prompt();before=byte(0xf3d8)
        type_command(port,queue,line,deadline)
        try:
            wait_byte(0xf3d8,(before+1)&255,deadline);prompt()
        except Exception:
            capture('failure-console',segments['LOWBSS'][0],0x558)
            capture('failure-bank0',0,0xffff)
            capture('failure-bank1',0,0xffff,'worker')
            (work/'failure-registers.txt').write_bytes(sp.monitor_command(port,'r'))
            raise
        data=capture('console',segments['LOWBSS'][0],0x558)
        if contains.encode() not in data: raise AssertionError((line,data))
        checks.append(dict(command=line));print('PASS',line,flush=True)

    def click_at(x,y):
        sp.write_kernel_blocks(port,[(click,bytes((handle,x,0,y)))])
        deadline=time.monotonic()+90
        while capture('click',click,1)!=b'\0':
            if time.monotonic()>deadline: raise TimeoutError('editor did not consume click')
            time.sleep(.05)

    def pointer(x,y,buttons):
        if not patched:
            for name,length,offsets in (('x',10,((3,0),(6,1))),('y',4,((1,2),)),('buttons',4,((1,3),))):
                where=exports['_udeks_pointer_'+name][0];original=capture('pointer-'+name,where,length)
                expected={'x':b'\x08\x78\xad\xd8\xf1\xae\xd9\xf1\x28\x60',
                    'y':b'\xad\xda\xf1\x60','buttons':b'\xad\xdb\xf1\x60'}[name]
                if original!=expected: raise ValueError('pointer getter changed')
                patched.append((where,original));data=bytearray(original)
                for offset,relative in offsets:data[offset:offset+2]=(scratch+relative).to_bytes(2,'little')
                sp.write_kernel_blocks(port,[(scratch,bytes((12,0,40,0))),(where,data)])
        sp.write_kernel_blocks(port,[(scratch,(x+12).to_bytes(2,'little')+bytes((y+40,buttons)))])

    def drag_to(x,y):
        pointer(origin[0]+8,origin[1]+5,0)
        wait_byte(0xf24d,0,time.monotonic()+90)
        pointer(origin[0]+8,origin[1]+5,1)
        wait_byte(0xf248,handle,time.monotonic()+90)
        pointer(x+8,y+5,1)
        wait_byte(0xf249,x,time.monotonic()+90)
        pointer(x+8,y+5,0)
        wait_byte(0xf248,0,time.monotonic()+90)
        sp.write_kernel_blocks(port,patched);patched.clear()
        origin[:]=[x,y]

    def screen(tag,sprite=None):
        deadline=time.monotonic()+90
        while True:
            start,end,_=segments['VICSHADOW']
            shadow,bitmap=sp.capture_blocks(port,[(work/(tag+'-shadow.bin'),start,end,'kernel'),
                (work/(tag+'-bitmap.bin'),0x6000,0x7f3f,'worker')])
            if shadow==bitmap and (sprite is None or sprite_matches(bitmap,sprite,origin)): break
            if time.monotonic()>deadline: raise AssertionError(('screen mismatch',tag))
            time.sleep(.1)
        (work/(tag+'.png')).write_bytes(bitmap_preview(bitmap))
        checks.append(dict(screen=tag,exact_sprite=sprite is not None))
        print('PASS',tag,flush=True)
        return bitmap

    try:
        wait_byte(0xf3e0,2,time.monotonic()+240)
        command('xsprdef &');wait_byte(0xf246,1,time.monotonic()+120)
        handle=byte(0xf247)
        selected=capture('selected',exports['_udeks_banked_graphics_selected'][0],1)[0]
        if selected!=0: raise AssertionError('disk editor should require joined allocation')
        task,base,limit,stack,_,_=JOINED_ALLOCATION
        edit=app['_udeks_xsprdef_pixels'][0]-0x1000+base
        # The formerly dead bottom-right edge of button eight.
        click_at(231,99);screen('blank',bytes(63))
        pattern=bytearray(0xaa if row%2==0 else 0x55 for row in range(21) for _ in range(3))
        sp.write_blocks(port,[(edit,pattern)],'worker')
        # A fixture-only buffer poke is not a pixel delta. Two real Invert
        # actions publish the complete new pattern before timing clicks.
        click_at(208,130);screen('fixture-inverted',bytes(b^255 for b in pattern))
        click_at(208,130)
        screen('checkerboard',pattern)
        sp.monitor_command(port,'warp off')
        reply=sp.monitor_command(port,'warp')
        (work/'warp-off.txt').write_bytes(reply)
        if b'Warp mode is off.' not in reply: raise AssertionError('timing requires warp off')
        for number,(sx,sy) in enumerate(((0,0),(23,20),(7,7),(8,8),(12,10))):
            for toggle in range(2):
                before=screen('before-click',pattern)
                compositions=int.from_bytes(capture('composition-count',0xf25e,2),'little')
                started=time.monotonic()
                click_at(8+sx*8,20+sy*8);pattern[sy*3+sx//8]^=128>>(sx%8)
                after=screen(f'pixel-{number}-{toggle}',pattern)
                elapsed=time.monotonic()-started
                count=(int.from_bytes(capture('composition-count',0xf25e,2),'little')-compositions)&65535
                if args.expect_delta and count: raise AssertionError(('pixel caused full repaint',count))
                expected=bytearray(before)
                for ox,oy,scale in ((8,20,8),(208,20,1)):
                    for dy in range(scale):
                        for dx in range(scale):
                            x=origin[0]+ox+sx*scale+dx;y=origin[1]+oy+sy*scale+dy
                            expected[(y//8)*320+(x//8)*8+y%8]^=128>>(x%8)
                if after!=expected: raise AssertionError('pixel changed outside the two cells')
                checks.append(dict(pixel=(sx,sy),toggle=toggle,full_compositions=count,
                    wall_seconds_including_monitor=elapsed))
                print('PIXEL',sx,sy,'toggle',toggle,'seconds',round(elapsed,3),'compositions',count,flush=True)
        sp.monitor_command(port,'warp on')
        for x,y in ((37,7),(40,0),(4,4)):
            drag_to(x,y);screen(f'drag-{x}-{y}',pattern)
            click_at(199,187);pattern[62]^=1
            screen(f'after-drag-click-{x}-{y}',pattern)
        click_at(231,76);screen('save-confirmation')
        click_at(150,123);screen('cancel-confirmation',pattern)
        click_at(208,52);screen('confirm-again')
        click_at(150,123);screen('save-cancelled',pattern)
        click_at(208,78);screen('session-list')
        click_at(231,99);screen('session-reopened',pattern)
        click_at(231,154);screen('inverted',bytes(b^255 for b in pattern))
        click_at(231,128);screen('cleared',bytes(63))
        click_at(208,78);screen('kept-clear-list')
        click_at(231,99);screen('kept-clear-reopened',bytes(63))
        sp.write_blocks(port,[(edit,pattern)],'worker')
        click_at(208,130);click_at(208,130);screen('restored-pattern',pattern)
        command('xclock &');wait_byte(0xf246,2,time.monotonic()+120)
        command('xdraw &');wait_byte(0xf246,3,time.monotonic()+120)
        command('cowsay sprite test','sprite test');screen('three-apps')
        # Cover/uncover the edited bitmap. Real client clicks are focused-only;
        # background delta fallback is exercised by the service host tests.
        for name,count in (('xdraw',2),('xclock',1)):
            command(name+' -q');wait_byte(0xf246,count,time.monotonic()+120)
        screen('uncovered-after-edit',pattern)
        for task,base,limit,stack,_,_ in (JOINED_ALLOCATION,*ALLOCATIONS[2:]):
            for offset in (0,0xb0):
                if capture(f'guard-{task}-{offset}',stack+offset,16,'worker')!=b'\xa5'*16:
                    raise AssertionError(('stack guard',task,offset))
        command('xinit -q');wait_byte(0xf246,0,time.monotonic()+120)
        command('echo editor cleanup passed','editor cleanup passed')
        if byte(0xf11b): raise AssertionError('task canary failure')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive,
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),checks=checks),indent=2)+'\n')
    finally:
        sp.terminate(proc,port)
        if master is not None: os.close(master)


if __name__=='__main__': main()

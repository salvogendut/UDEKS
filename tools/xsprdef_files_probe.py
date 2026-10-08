#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Sprite Save/Load through real native file requests on disposable media.

Dialog/pixel clicks use the WM event queue, not a physical mouse; no app data,
file request/reply, permissions or storage-service state is injected. A fresh
VICE process reads the saved bank on boot two. Original media is never attached.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from storage_shell_probe import sp, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port
from storage_public_probe import files
from xsprdef_probe import sprite_matches
from xcalc_probe import bitmap_preview
from xsprdef_basic_probe import basic_bank, qualify as basic_qualify

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--drive',choices=('1541','1571','1581'),required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'build/sprite-files')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='files-'+args.drive+'-',dir=args.output.resolve()))
    original=args.disk.read_bytes();disk=work/('disposable'+args.disk.suffix);disk.write_bytes(original)
    text=(ROOT/'build/8502/udeks-8502.map').read_text();exports=map_exports(text);segments=map_segments(text)
    app=map_exports((ROOT/'build/user/native-xsprdef/xsprdef.map').read_text())
    def app_address(name):return app['_udeks_xsprdef_'+name][0]-0x1000+0x2300
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    wm=re.search(r'^window_manager\.o:\n((?:[ \t].*\n)+)',text,re.M)[1]
    click=segments['BSS'][0]+int(re.search(r'BSS\s+Offs=([0-9A-F]+)\s+Size=000004',wm)[1],16)
    expected=bytearray(504);expected[7*63]=128;expected[503]=1
    checks=[]
    print('Evidence:',work,flush=True)
    for boot in range(2):
        port=choose_port()
        proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
            ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),
            log_path=work/f'vice-{boot}.log')
        def capture(tag,address,size,bank='kernel'):
            return sp.capture_blocks(port,[(work/f'{boot}-{tag}.bin',address,address+size-1,bank)])[0]
        def byte(address,bank='kernel'):return capture('byte',address,1,bank)[0]
        def wait(address,value,bank='kernel',timeout=180):
            deadline=time.monotonic()+timeout
            while True:
                try:
                    if byte(address,bank)==value:return
                except ConnectionRefusedError:
                    if proc.poll() is not None:raise
                if time.monotonic()>deadline:raise TimeoutError((hex(address),value))
                time.sleep(.05)
        def prompt():
            deadline=time.monotonic()+180
            while capture('root',slots+1,2)!=b'\4\2':
                if time.monotonic()>deadline:raise TimeoutError('shell prompt')
                time.sleep(.05)
        def command(line,contains=''):
            prompt();previous=byte(0xf3d8);type_command(port,queue,line,time.monotonic()+180)
            wait(0xf3d8,(previous+1)&255);prompt()
            data=capture('console',segments['LOWBSS'][0],0x558)
            if contains.encode() not in data:raise AssertionError((line,data))
            checks.append(dict(boot=boot,command=line));print('PASS',boot,line,flush=True)
        def click_at(x,y):
            sp.write_kernel_blocks(port,[(click,bytes((handle,x,0,y)))])
            wait(click,0)
        def dialog(op,error=None,editor=True,cancel=False):
            click_at(208 if editor else (80 if op==1 else 200 if op==4 else 140),
                     (52 if op==1 else 156) if editor else 120)
            wait(app_address('dialog'),op,'worker')
            click_at(150 if cancel else 92,123)
            wait(app_address('dialog'),0 if cancel else 3,'worker')
            if not cancel:
                actual=byte(app_address('file_error'),'worker')
                if actual!=error:raise AssertionError(('file error',op,error,actual))
                # Preserve the actual rendered result dialog before dismissing.
                screen(f'dialog-{op}-{error}')
                click_at(92,123);wait(app_address('dialog'),0,'worker')
            checks.append(dict(boot=boot,operation=op,cancelled=cancel,errno=error))
            print('PASS',boot,{1:'save',2:'load',4:'export'}[op],'cancel' if cancel else error,flush=True)
        def screen(tag,sprite=None):
            deadline=time.monotonic()+120
            while True:
                start,end,_=segments['VICSHADOW']
                shadow,bitmap=sp.capture_blocks(port,[(work/f'{boot}-{tag}-shadow.bin',start,end,'kernel'),
                    (work/f'{boot}-{tag}-bitmap.bin',0x6000,0x7f3f,'worker')])
                if shadow==bitmap and (sprite is None or sprite_matches(bitmap,sprite)):break
                if time.monotonic()>deadline:raise AssertionError(('screen',tag))
                time.sleep(.1)
            (work/f'{boot}-{tag}.png').write_bytes(bitmap_preview(bitmap))
        def bank_matches():
            actual=capture('sprite-bank',app_address('bank'),504,'worker')
            if actual!=expected:raise AssertionError('sprite bank differs from exact saved bytes')
        try:
            wait(0xf3e0,2,timeout=240);command('xsprdef &');wait(0xf246,1)
            if byte(exports['_udeks_banked_graphics_selected'][0])!=0:raise AssertionError('not joined app')
            handle=byte(0xf247)
            if capture('empty-bank',app_address('bank'),504,'worker')!=bytes(504):raise AssertionError('BSS not fresh')
            if boot==0:
                click_at(231,99);click_at(8,20);click_at(199,187)
                screen('edited',expected[441:])
                dialog(1,cancel=True);screen('save-cancelled',expected[441:])
                command('mount -o remount,ro 8 /','ready (read-only)')
                dialog(1,30);bank_matches() # RO save reports failure; edits survive
                dialog(2,2);bank_matches();screen('missing-kept-edit',expected[441:])
                command('mount -o remount,rw 8 /','ready (read-write)')
                dialog(1,0);bank_matches()
                click_at(16,20);changed=bytearray(expected[441:]);changed[0]^=64
                screen('unsaved',changed)
                dialog(1,17);screen('duplicate-kept-edit',changed)
                dialog(2,cancel=True);screen('load-cancelled',changed)
                dialog(2,0);bank_matches();screen('loaded',expected[441:])
                click_at(208,78) # B keeps edits and returns to list
                dialog(4,editor=False,cancel=True)
                dialog(4,0,editor=False)
                dialog(4,17,editor=False)
                command('mount -o remount,ro 8 /','ready (read-only)')
                dialog(4,30,editor=False)
                click_at(231,99);screen('exported-kept-bank',expected[441:])
            else:
                command('df','Read-write mount')
                dialog(2,0,editor=False);bank_matches()
                click_at(231,99);screen('reboot-loaded',expected[441:])
            command('xdraw &');wait(0xf246,2);command('xdraw -q');wait(0xf246,1)
            screen('uncovered',expected[441:]);command('cowsay sprite files','sprite files')
            for address in (0x3f00,0x3fb0):
                if capture('stack-'+hex(address),address,16,'worker')!=b'\xa5'*16:raise AssertionError('stack guard')
            command('xsprdef -q');wait(0xf246,0)
            if byte(0xf11b):raise AssertionError('lifecycle canary')
        finally:
            sp.terminate(proc,port)
            if master is not None:os.close(master)
    before,after=files(original),files(disk.read_bytes())
    for name,value in before.items():
        if after.get(name)!=value:raise AssertionError(('existing file changed',name))
    if {n:v for n,v in after.items() if n not in before}!={b'SPRITES.SPR':bytes(expected),
                                                         b'SPRITES.BSV':basic_bank(expected)}:
        raise AssertionError('created bank file not exact or duplicate save changed it')
    if args.disk.read_bytes()!=original:raise AssertionError('source disk modified')
    result=dict(drive=args.drive,checks=checks,original_files_unchanged=len(before),
                disk_sha256=hashlib.sha256(original).hexdigest(),
                written_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),
                bank_sha256=hashlib.sha256(expected).hexdigest())
    result['basic']=basic_qualify(disk,args.drive,work/'basic')
    (work/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS sprite persistence, errors, cancellation, reboot and existing-file preservation:',work,flush=True)

if __name__=='__main__':main()

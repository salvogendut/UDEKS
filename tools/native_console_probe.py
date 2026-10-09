#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Foreground native console execution without kernel changes (VICE proof).

Shell keyboard events and test-only pointer getters exercise normal dispatch.
No monitor call starts a task or fabricates its output. Arguments, stdin,
background arbitration and foreground exit-status reporting are not claimed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from add_disk_apps import add_apps
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_app_layout import ALLOCATIONS, fitting_allocations
from o65_to_udex import relocate_executable
from storage_shell_probe import sp,byte,keyboard_queue_address,type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port
from xcalc_probe import pointer_test_scratch

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format',choices=('d64','d71','d81'),default='d81')
    args=parser.parse_args()
    out=ROOT/'build/native-console/vice'; out.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix=args.format+'-',dir=out))
    original=(ROOT/f'build/boot/udeks.{args.format}').read_bytes()
    program=(ROOT/'build/native-console/ticker/TICKER.BIN').read_bytes()
    if 6 not in fitting_allocations(program):
        raise ValueError('probe requires the console example to fit the smallest slot')
    _,base,limit,stack,_,_=next(row for row in ALLOCATIONS if row[0]==6)
    fixture=add_apps(original,[('TICKER.BIN',program),('PULSE.BIN',program)])
    disk=work/('test.'+args.format); disk.write_bytes(fixture)
    text=(ROOT/'build/8502/udeks-8502.map').read_text()
    exports=map_exports(text); segments=map_segments(text)
    scheduler=(ROOT/'build/8502/udeks-scheduler-overlay.map').read_text()
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    timer=map_exports(scheduler)['_udeks_task_wait_selector_private'][0]
    app=map_exports((ROOT/'build/native-console/ticker/program.map').read_text())
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    scratch=pointer_test_scratch(text)
    port=choose_port(); records=[]; patched=[]
    drive=dict(d64='1541',d71='1571',d81='1581')[args.format]
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',drive),log_path=work/'vice.log')

    def capture(tag,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),address,address+size-1,bank)])[0]
    def screen():
        data=capture('console',segments['LOWBSS'][0],0x558)
        return '\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
    def until(test,label,seconds=90):
        deadline=time.monotonic()+seconds
        while not test():
            if time.monotonic()>deadline: raise AssertionError((label,screen()))
            time.sleep(.05)
    def prompt():
        until(lambda:capture('prompt',slots+1,2)==b'\4\2','prompt')
    def command(line,foreground=False):
        prompt(); before=byte(port,0xf3d8)
        type_command(port,queue,line,time.monotonic()+120)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,time.monotonic()+120)
        if not foreground: prompt()
        records.append(dict(command=line,console=screen()))
        print('PASS',line,flush=True)
    def step():
        return capture('ticker-step',app['_ticker_step'][0]-0x1000+base,1,'worker')[0]
    def verify_ticker(tag):
        until(lambda:step()==6,'ticker complete')
        prompt()
        expected='ticker: native task started\nticker: stderr works\n'+''.join(
            'tick '+str(n)+'\n' for n in range(1,6))+'ticker: complete'
        if expected not in screen(): raise AssertionError('missing or reordered console output')
        for label,expected in (('_ticker_failure',b'\0'),('_ticker_private',b'1234')):
            if capture(tag+label,app[label][0]-0x1000+base,len(expected),'worker')!=expected:
                raise AssertionError('private state failed')
        until(lambda:capture('reaped',slots+41,1)==b'\0','native reap')
        installed=relocate_executable(program,base,limit-base)[16:]
        if capture(tag+'-code',base,len(installed),'worker')!=installed:
            raise AssertionError('native code damaged')
        for offset in (0,0xb0):
            if capture(tag+'-guard-'+str(offset),stack+offset,16,'worker')!=b'\xa5'*16:
                raise AssertionError('native stack guard')
        records.append(dict(check=tag,console=screen(),private_state=True,code_and_guards=True))
    def pointer(x,y,buttons):
        if not patched:
            for name,length,offsets in (('x',10,((3,0),(6,1))),('y',4,((1,2),)),('buttons',4,((1,3),))):
                address=exports['_udeks_pointer_'+name][0]
                old=capture('pointer-'+name,address,length)
                expected={'x':b'\x08\x78\xad\xd8\xf1\xae\xd9\xf1\x28\x60',
                          'y':b'\xad\xda\xf1\x60','buttons':b'\xad\xdb\xf1\x60'}[name]
                if old!=expected: raise ValueError('pointer getter changed')
                patched.append((address,old)); new=bytearray(old)
                for offset,relative in offsets: new[offset:offset+2]=(scratch+relative).to_bytes(2,'little')
                sp.write_kernel_blocks(port,[(scratch,bytes((12,0,40,0))),(address,new)])
        sp.write_kernel_blocks(port,[(scratch,(x+12).to_bytes(2,'little')+bytes((y+40,buttons)))])

    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        prompt()
        sp.monitor_command(port,'warp off')
        if b'Warp mode is off.' not in sp.monitor_command(port,'warp'):
            raise AssertionError('timed observation requires warp off')
        vic=capture('vic-before',0xf1b0,24)
        command('ticker',True)
        until(lambda:step()==1,'first private task step')
        if byte(port,0xf246)!=0: raise AssertionError('console task opened a window')
        verify_ticker('solo')
        if capture('vic-after',0xf1b0,24)!=vic: raise AssertionError('console task changed VIC state')
        command('xclock &')
        sp.wait_for_byte(port,0xf246,1,time.monotonic()+120)
        handle=byte(port,0xf247)
        command('pulse',True)       # same file, independent name, clean BSS
        until(lambda:step()==1,'second private task step')
        # Task 4's sleep deadline must advance WHILE task 6 owns foreground.
        before=capture('clock-deadline',timer+3,1)
        until(lambda:capture('clock-deadline-after',timer+3,1)!=before,'clock scheduled')
        pointer(134,55,0); sp.wait_for_byte(port,0xf24d,0,time.monotonic()+30)
        pointer(134,55,1); sp.wait_for_byte(port,0xf248,handle,time.monotonic()+30)
        pointer(150,71,1); sp.wait_for_byte(port,0xf249,140,time.monotonic()+30)
        live_step=step()
        if not 1<=live_step<=5: raise AssertionError('drag did not overlap console execution')
        pointer(150,71,0); sp.wait_for_byte(port,0xf248,0,time.monotonic()+30)
        sp.write_kernel_blocks(port,patched); patched.clear()
        records.append(dict(check='clock-and-drag-during-console',ticker_step=live_step))
        verify_ticker('with-clock')
        if byte(port,0xf246)!=1: raise AssertionError('clock window lost')
        command('echo native console returned')
        command('xclock -q')
        if byte(port,0xf11b): raise AssertionError('task canary failure')
        if (ROOT/f'build/boot/udeks.{args.format}').read_bytes()!=original:
            raise AssertionError('source disk changed during the probe')
        report=dict(scope='foreground no-argument native stdout/stderr/sleep execution proof',
                    source_disk_sha256=hashlib.sha256(original).hexdigest(),
                    fixture_sha256=hashlib.sha256(fixture).hexdigest(),
                    program_sha256=hashlib.sha256(program).hexdigest(),drive=drive,
                    source_disk_unchanged=True,arguments=False,stdin=False,background_policy=False,
                    shell_exit_status=False,records=records)
        (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS native console; evidence:',work,flush=True)
    finally:
        try:
            if patched: sp.write_kernel_blocks(port,patched)
        finally:
            sp.terminate(proc,port); os.close(master)


if __name__=='__main__': main()

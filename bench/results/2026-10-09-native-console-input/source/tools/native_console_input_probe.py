#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Foreground canonical input and background denial through real task gates.

Disposable disks, keyboard-queue injection only; no task/request/code mutation.
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
from native_app_layout import ALLOCATIONS
from storage_shell_probe import sp,keyboard_queue_address,type_command,wait_keyboard_queue
from task_waitpid_probe import scheduler_symbols
from task_cancel_probe import wait_symbols
from vice_capture import choose_port

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--format',choices=('d64','d81'),default='d81')
    p.add_argument('--warp',action='store_true',help='accelerate functional checks (no timing claim)')
    args=p.parse_args()
    out=ROOT/'build/native-console/input'; out.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix=args.format+'-',dir=out))
    source=(ROOT/f'build/boot/udeks.{args.format}').read_bytes()
    apps={n:(ROOT/f'build/native-console/{n.lower()}/{n}.BIN').read_bytes() for n in ('ASK','BGREAD')}
    fixture=add_apps(source,[(n+'.BIN',data) for n,data in apps.items()])
    disk=work/('test.'+args.format); disk.write_bytes(fixture)
    kernel=(ROOT/'build/8502/udeks-8502.map').read_text()
    exports=map_exports(kernel); segments=map_segments(kernel)
    queue=keyboard_queue_address(kernel,(ROOT/'build/8502/keyboard.s').read_text())
    scheduler=ROOT/'build/8502/udeks-scheduler-overlay.map'
    slots=scheduler_symbols(scheduler)['_udeks_lifecycle_slots_private']
    waits=wait_symbols(scheduler)
    app={n:map_exports((ROOT/f'build/native-console/{n.lower()}/program.map').read_text()) for n in apps}
    port=choose_port(); records=[]
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type','1541' if args.format=='d64' else '1581'),
        log_path=work/'vice.log')

    def capture(tag,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),address,address+size-1,bank)])[0]
    def kernel_byte(address):
        return capture('kernel-byte-'+hex(address),address,1)[0]
    def screen():
        data=capture('console',segments['LOWBSS'][0],0x558)
        return '\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
    def wait(test,label,seconds=120):
        deadline=time.monotonic()+seconds
        while not test():
            if time.monotonic()>deadline: raise AssertionError((label,screen()))
            time.sleep(.04)
    def prompt(): wait(lambda:capture('prompt',slots+1,2)==b'\4\2','shell prompt')
    def command(line,foreground=False):
        prompt(); before=kernel_byte(0xf3d8)
        type_command(port,queue,line,time.monotonic()+120)
        wait(lambda:kernel_byte(0xf3d8)==(before+1)&255,'command consumed')
        if not foreground: prompt()
    def events(text):
        for start in range(0,len(text),16):
            batch=text[start:start+16]
            wait_keyboard_queue(port,queue,time.monotonic()+30)
            data=b''.join(bytes((1,0xff,ch,0)) for ch in batch)
            sp.write_kernel_blocks(port,[(queue,data),(queue+64,bytes((len(batch)%16,0,len(batch))))])
        wait_keyboard_queue(port,queue,time.monotonic()+30)
    def blocked(task): return capture('task'+str(task),slots+(task-1)*8,8)[1:3]==b'\4\2'
    def app_value(name,task,symbol):
        base=next(row[1] for row in ALLOCATIONS if row[0]==task)
        return capture(symbol,app[name]['_'+symbol][0]-0x1000+base,1,'worker')[0]
    def ask(task,text,keys=None):
        command('ask',True); wait(lambda:blocked(task),'ask INPUT wait')
        tag='input-'+str(len(records))
        capture(tag+'-waiting',slots+(task-1)*8,8)
        if kernel_byte(waits['operation']+task-1)!=16: raise AssertionError('not POLL')
        before=kernel_byte(0xf3d8)
        if keys is None: type_command(port,queue,text,time.monotonic()+90)
        else: events(keys+b'\n')
        prompt()
        expected=text+'\n'+text+'\nUDEKS:~>'
        if not screen().endswith(expected): raise AssertionError(('echo mismatch',screen(),expected))
        after=kernel_byte(0xf3d8)
        if after!=before: raise AssertionError(('application line executed by shell',before,after,screen()))
        if app_value('ASK',task,'ask_stage')!=3 or app_value('ASK',task,'ask_error'):
            raise AssertionError('SDK read failed')
        command('echo $?')
        if not screen().endswith('echo $?\n0\nUDEKS:~>'): raise AssertionError('normal status')
        capture(tag+'-reaped',slots+(task-1)*8,8)
        records.append(dict(check='input',tag=tag,task=task,text=text,status=0,console=screen()))
        print('PASS stdin',task,repr(text),flush=True)
    def cancel(task,partial):
        command('ask',True); wait(lambda:blocked(task),'cancel INPUT wait')
        events(partial.encode()); events(b'\3'); prompt()
        command('echo $?')
        if not screen().endswith('echo $?\n130\nUDEKS:~>'): raise AssertionError('cancel status')
        if capture('cancel-slot',slots+(task-1)*8,8)!=bytes(8): raise AssertionError('not reaped')
        for name,address in waits.items():
            if capture('cancel-'+name,address+task-1,1)!=b'\0': raise AssertionError('wait leaked')
        if kernel_byte(exports['_udeks_line_editor_submitted_ready_value'][0]): raise AssertionError('input leaked')
        records.append(dict(check='cancel',task=task,partial=partial,status=130))
        print('PASS cancel partial stdin',task,flush=True)

    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240); prompt()
        sp.monitor_command(port,'warp on' if args.warp else 'warp off')
        vic=capture('vic-before',0xf1b0,24)
        ask(6,'MiXeD input 123')
        ask(6,'edit me',b'edit mx\be')
        ask(6,'')
        ask(6,'0123456789'*5+'abcd')
        if capture('vic-after',0xf1b0,24)!=vic: raise AssertionError('stdin started VIC')
        cancel(6,'do not execute this')
        command('bgread &'); wait(lambda:app_value('BGREAD',6,'input_checks')>0,'background denial')
        start=app_value('BGREAD',6,'input_checks')
        events(b'echo retained')
        wait(lambda:app_value('BGREAD',6,'input_checks')!=start,'background denied during edit')
        before=kernel_byte(0xf3d8)
        events(b'\n')
        wait(lambda:kernel_byte(0xf3d8)==(before+1)&255,'edited shell line consumed')
        prompt()
        if not screen().endswith('echo retained\nretained\nUDEKS:~>'): raise AssertionError('background stole shell input')
        command('xclock &'); sp.wait_for_byte(port,0xf246,1,time.monotonic()+120)
        ask(5,'reader with peers')
        command('xdraw &'); sp.wait_for_byte(port,0xf246,2,time.monotonic()+120)
        ask(3,'third allocation')
        command('xclock -q'); wait(lambda:kernel_byte(slots+25)==0,'clock retired')
        ask(4,'fourth allocation')
        cancel(4,'discard me')
        command('bgread &'); wait(lambda:app_value('BGREAD',4,'input_checks')>0,'second background reader')
        ask(3,'two background readers')
        for task in (4,6):
            if app_value('BGREAD',task,'input_failure') or not app_value('BGREAD',task,'input_checks'):
                raise AssertionError('background SDK/raw READ/POLL denial failed')
        if kernel_byte(0xf246)!=1 or kernel_byte(0xf11b): raise AssertionError('peer/canary failed')
        records.append(dict(check='background-denial',tasks=[4,6],errno=5,raw_read=True,poll=True))
        if (ROOT/f'build/boot/udeks.{args.format}').read_bytes()!=source: raise AssertionError('source disk changed')
        report=dict(scope='canonical foreground stdin; keyboard-queue injection, no native mouse/hardware claim',
            format=args.format,warp=args.warp,source_disk_sha256=hashlib.sha256(source).hexdigest(),
            fixture_sha256=hashlib.sha256(fixture).hexdigest(),
            apps={n:hashlib.sha256(data).hexdigest() for n,data in apps.items()},checks=records)
        (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS native console input:',work,flush=True)
    finally:
        sp.terminate(proc,port); os.close(master)


if __name__=='__main__': main()

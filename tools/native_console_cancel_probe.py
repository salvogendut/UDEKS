#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ctrl+C through the terminal and real parent CANCEL, never a window event.

Disposable disks; ordinary shell commands and keyboard-queue events. Observe
real scheduler/storage state; do not patch requests, lifecycle or program code.
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
from storage_shell_probe import sp,byte,keyboard_queue_address,type_command
from task_waitpid_probe import scheduler_symbols
from task_cancel_probe import wait_symbols
from vice_capture import choose_port

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--format',choices=('d64','d81'),default='d81')
    args=p.parse_args()
    out=ROOT/'build/native-console/cancel'; out.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix=args.format+'-',dir=out))
    source=(ROOT/f'build/boot/udeks.{args.format}').read_bytes()
    nap=(ROOT/'build/native-console/nap/NAP.BIN').read_bytes()
    ticker=(ROOT/'build/native-console/ticker/TICKER.BIN').read_bytes()
    fixture=add_apps(source,[('NAP.BIN',nap),('TICKER.BIN',ticker)])
    disk=work/('test.'+args.format); disk.write_bytes(fixture)
    kernel=(ROOT/'build/8502/udeks-8502.map').read_text()
    segments=map_segments(kernel)
    queue=keyboard_queue_address(kernel,(ROOT/'build/8502/keyboard.s').read_text())
    scheduler=ROOT/'build/8502/udeks-scheduler-overlay.map'
    slots=scheduler_symbols(scheduler)['_udeks_lifecycle_slots_private']
    waits=wait_symbols(scheduler)
    generation=map_exports((ROOT/'build/storage/module.map').read_text())['_udeks_storage_generations'][0]
    loader=map_exports((ROOT/'build/boot/banked-loader.map').read_text())
    owned=loader['banked_owned'][0]
    app=map_exports((ROOT/'build/native-console/nap/program.map').read_text())
    port=choose_port(); records=[]
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type','1541' if args.format=='d64' else '1581'),
        log_path=work/'vice.log')

    def capture(tag,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),address,address+size-1,bank)])[0]
    def screen():
        data=capture('console',segments['LOWBSS'][0],0x558)
        return '\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
    def wait(test,label,seconds=120):
        deadline=time.monotonic()+seconds
        while not test():
            if time.monotonic()>deadline: raise AssertionError((label,screen()))
            time.sleep(.05)
    def prompt(): wait(lambda:byte(port,0xf184)==0 and capture('prompt',slots+1,2)==b'\4\2','prompt')
    def command(line,foreground=False):
        prompt(); before=byte(port,0xf3d8)
        sp.monitor_command(port,'warp on') # accelerate disk delivery, not cancellation observations
        type_command(port,queue,line,time.monotonic()+120)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,time.monotonic()+120)
        if not foreground: prompt()
        sp.monitor_command(port,'warp off')
        print('PASS',line,flush=True)
    def ctrl_c():
        sp.write_kernel_blocks(port,[(queue,bytes((1,0xff,3,2))),(queue+64,bytes((1,0,1)))])
    def steps(task,tag):
        base=next(row[1] for row in ALLOCATIONS if row[0]==task)
        return capture(tag,base+app['_nap_steps'][0]-0x1000,2,'worker')
    def generation_of(task,tag): return capture(tag,generation+task,1,'worker')[0]
    def blocked(task):
        return byte(port,slots+(task-1)*8+1)==4 and byte(port,waits['state']+task-1)==1
    def cancel(task,graphical=False,peers=()):
        tag='clock' if graphical else 'slot'+str(task)
        # One atomic observation: a clock can legitimately become RUNNABLE
        # between separate monitor reads of state and wait reason.
        wait(lambda:capture(tag+'-before',slots+(task-1)*8,8)[:3]==bytes((1,4,3)),
             'sleeping root child')
        if byte(port,0xf184)!=1<<(task-3): raise AssertionError('wrong foreground owner')
        peer_generations={peer:generation_of(peer,tag+'-peer'+str(peer)+'-before') for peer in peers}
        old_gen=generation_of(task,tag+'-generation-before')
        if not graphical: old_steps=steps(task,tag+'-steps-before')
        ctrl_c()
        prompt()
        if 'Interrupted\n' not in screen(): raise AssertionError('missing confirmed cancellation notice')
        if byte(port,0xf17a)!=130: raise AssertionError('foreground cancellation status lost')
        if capture(tag+'-after',slots+(task-1)*8,8)!=bytes(8): raise AssertionError('not reaped')
        if capture(tag+'-owned',owned+task-3,1,'worker')!=b'\0': raise AssertionError('allocation still owned')
        if generation_of(task,tag+'-generation-after')!=(old_gen+1)&255: raise AssertionError('retirement hook not run exactly once')
        for name,address in waits.items():
            if capture(tag+'-wait-'+name,address+task-1,1)!=b'\0': raise AssertionError('stale wait '+name)
        for peer,gen in peer_generations.items():
            if generation_of(peer,tag+'-peer'+str(peer)+'-after')!=gen or byte(port,slots+(peer-1)*8+1) in (0,6):
                raise AssertionError('peer retired')
        if not graphical and steps(task,tag+'-steps-after')!=old_steps: raise AssertionError('cancelled task resumed')
        command('echo $?')
        console=screen()
        if not console.endswith('echo $?\n130\nUDEKS:~>'): raise AssertionError('ush did not report 130')
        records.append(dict(check=tag,task=task,peers=list(peers),status=130,console=console))
        print('PASS cancelled',tag,flush=True)

    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240); prompt()
        sp.monitor_command(port,'warp off')
        # Without graphics: a non-returning task must actually be cancelled.
        vic=capture('vic-before',0xf1b0,24)
        command('nap alpha',True); cancel(6)
        if capture('vic-after',0xf1b0,24)!=vic: raise AssertionError('console cancel started VIC')
        # Cross the old ten-second deadline before reusing its memory. A dead
        # request must not wake up and resume after the shell regained input.
        old=steps(6,'retired-steps-before')
        ticks=map_exports(scheduler.read_text())['_udeks_monotonic_ticks_low'][0]
        start=int.from_bytes(capture('ticks-before',ticks,2),'little')
        wait(lambda:(int.from_bytes(capture('ticks-after',ticks,2),'little')-start)&65535>=620,'old sleep deadline',30)
        if steps(6,'retired-steps-after')!=old: raise AssertionError('stale sleep resumed')
        command('ticker normal',True); prompt()
        command('echo $?')
        if not screen().endswith('echo $?\n37\nUDEKS:~>'): raise AssertionError('slot reuse/natural completion')
        records.append(dict(check='reuse-natural-exit',status=37))
        command('xclock &'); wait(lambda:byte(port,0xf246)==1,'clock')
        command('nap &'); wait(lambda:blocked(6),'silent peer')
        command('nap second',True); cancel(5,peers=(4,6))
        command('xdraw &'); wait(lambda:byte(port,0xf246)==2,'draw peer')
        command('nap third',True); cancel(3,peers=(4,5,6))
        command('xclock -q'); wait(lambda:byte(port,slots+25)==0,'clock closed')
        command('nap fourth',True); cancel(4,peers=(5,6))
        command('xclock',True); wait(lambda:byte(port,0xf246)==2,'foreground clock')
        cancel(4,True,peers=(5,6)); wait(lambda:byte(port,0xf246)==1,'clock window cleanup')
        # Ctrl+C at the prompt must not target the remaining background jobs.
        generations=capture('idle-generations-before',generation+5,2,'worker')
        ctrl_c(); wait(lambda:byte(port,queue+66)==0,'prompt interrupt consumed')
        command('echo peers still running')
        if capture('idle-generations-after',generation+5,2,'worker')!=generations:
            raise AssertionError('prompt interrupt retired background job')
        if byte(port,0xf246)!=1 or byte(port,0xf11b): raise AssertionError('peer window/canary failed')
        if (ROOT/f'build/boot/udeks.{args.format}').read_bytes()!=source: raise AssertionError('source disk changed')
        report=dict(scope='task-based Ctrl+C; keyboard-queue input, no task/request injection',
            format=args.format,source_disk_sha256=hashlib.sha256(source).hexdigest(),
            fixture_sha256=hashlib.sha256(fixture).hexdigest(),nap_sha256=hashlib.sha256(nap).hexdigest(),
            ticker_sha256=hashlib.sha256(ticker).hexdigest(),stdin=False,background_policy=False,checks=records)
        (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS native console cancellation:',work,flush=True)
    finally:
        sp.terminate(proc,port); os.close(master)


if __name__=='__main__': main()

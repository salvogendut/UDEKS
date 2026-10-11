#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disk-loaded raw IPC fixtures through FF16; real EXIT/CANCEL retirement."""
import argparse
import hashlib
import json
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
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format',choices=('d64','d81'),default='d81');args=parser.parse_args()
    out=ROOT/'build/ipc/vice';out.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix=args.format+'-',dir=out))
    source=(ROOT/f'build/boot/udeks.{args.format}').read_bytes()
    image=(ROOT/'build/ipc/native/IPCTEST.BIN').read_bytes()
    disk=work/('test.'+args.format);disk.write_bytes(add_apps(source,[('IPCTEST.BIN',image)]))
    kernel=(ROOT/'build/8502/udeks-8502.map').read_text();exports=map_exports(kernel);segments=map_segments(kernel)
    queue=keyboard_queue_address(kernel,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    state=exports['_udeks_ipc_state'][0]
    symbols=map_exports((ROOT/'build/ipc/native/program.map').read_text())
    port=choose_port();records=[]
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type','1541' if args.format=='d64' else '1581'),log_path=work/'vice.log')
    def capture(tag,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),address,address+size-1,bank)])[0]
    def screen():
        data=capture('console',segments['LOWBSS'][0],0x558)
        return '\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
    def wait(test,label,seconds=120):
        deadline=time.monotonic()+seconds
        while not test():
            if proc.poll() is not None:raise AssertionError(('VICE exited',work/'vice.log'))
            if time.monotonic()>deadline:raise AssertionError((label,screen()))
            time.sleep(.05)
    def prompt():wait(lambda:byte(port,0xf184)==0 and capture('prompt',slots+1,2)==b'\4\2','prompt')
    def command(line,foreground=False):
        prompt();before=byte(port,0xf3d8);type_command(port,queue,line,time.monotonic()+120)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,time.monotonic()+120)
        if not foreground:prompt()
        print('PASS',line,flush=True)
    def pool():return capture('ipc-state',state,62,'kernel-flat')
    def owners():return pool()[:2]
    def row(task):return next(r for r in ALLOCATIONS if r[0]==task)
    def address(task,name):return row(task)[1]+symbols['_ipc_'+name][0]-0x1000
    def value(task,name,size=1):return capture(name+str(task),address(task,name),size,'worker')
    def check_app(task,phase):
        if value(task,'phase')!=bytes((phase,)) or value(task,'failure')!=b'\0':
            raise AssertionError(('fixture failed',task,value(task,'phase'),value(task,'failure')))
        _,base,limit,stack,_,_=row(task)
        code=relocate_executable(image,base,limit-base)[16:]
        if capture('installed'+str(task),base,len(code),'worker')!=code:raise AssertionError('app code changed')
        for offset in (0,0xb0):
            if capture('guard'+str(task)+str(offset),stack+offset,16,'worker')!=b'\xa5'*16:raise AssertionError('stack guard')
    def holder():
        wait(lambda:sum(bool(x) for x in owners())==1,'holder endpoint')
        task=next(x for x in owners() if x);check_app(task,1);return task
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240);prompt()
        if owners()!=b'\0\0':raise AssertionError('IPC not zero initialized')
        command('xclock &');clock=byte(port,0xf247)
        command('ipctest hold &');hold=holder();old=value(hold,'handle',2)
        free=[r[0] for r in ALLOCATIONS if r[0] in fitting_allocations(image) and r[0]!=hold]
        command('ipctest')
        test=next(t for t in free if value(t,'phase')==b'\3')
        check_app(test,3)
        if sum(bool(x) for x in owners())!=1 or any(pool()[6:8]):raise AssertionError('EXIT failed to purge sender/queued peer message')
        sp.write_blocks(port,[(address(hold,'release'),b'\1')],'worker')
        wait(lambda:owners()==b'\0\0','normal holder exit')
        check_app(hold,2)
        command('ipctest hold',True);hold=holder()
        if value(hold,'handle',2)==old:raise AssertionError('stale handle reused')
        sp.write_kernel_blocks(port,[(queue,bytes((1,0xff,3,2))),(queue+64,bytes((1,0,1)))])
        prompt();wait(lambda:owners()==b'\0\0','foreground CANCEL cleanup')
        command('echo $?')
        if '\n130\n' not in screen():raise AssertionError('cancel status')
        command('ipctest solo')
        if owners()!=b'\0\0':raise AssertionError('reuse cleanup')
        if byte(port,0xf246)!=1 or byte(port,0xf247)!=clock:raise AssertionError('clock lost during IPC')
        command('xclock -q');command('xinit -q');command('ipctest solo')
        if owners()!=b'\0\0':raise AssertionError('IPC coupled to graphics stop')
        command('echo IPC returned')
        if byte(port,0xf11b):raise AssertionError('task canary')
        if (ROOT/f'build/boot/udeks.{args.format}').read_bytes()!=source:raise AssertionError('source disk changed')
        report=dict(format=args.format,scope=__doc__,checks=['foreign access','16 exact copied bytes','full/empty/short receive','stale handle','sender EXIT purges peer queue','normal EXIT','foreground CANCEL','reuse','clock coexistence','graphics stopped'],disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256(image).hexdigest())
        (work/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS IPC:',work,flush=True)
    finally:
        if proc.poll() is None:
            try:sp.monitor_command(port,'quit')
            except (OSError,RuntimeError):proc.terminate()
        proc.wait(timeout=10)
if __name__=='__main__':main()

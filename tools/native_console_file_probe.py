#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Native SDK files, real EXIT/CANCEL cleanup, and shipped CAT alongside graphics.

Cold boots disposable media. Only keyboard events and the two fixture release
flags are written. No request/result, owner, scheduler or service is patched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from add_disk_apps import add_apps
import build_d81 as d81
from build_d71 import install_prg_file, sector_offset
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_app_layout import ALLOCATIONS
from o65_to_udex import relocate_executable
from storage_shell_probe import sp, keyboard_queue_address, type_command, wait_keyboard_queue
from storage_public_probe import files
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port

ROOT=Path(__file__).resolve().parents[1]
LONG=b''.join(('line %03d - native cat\n'%i).encode() for i in range(96))
PAYLOAD=b'\0\xff\x80Native\n'


def make_fixture(source,apps):
    image=bytearray(add_apps(source,[(n+'.BIN',data) for n,data in apps.items()]))
    install=d81.install_file if len(image)==d81.SIZE else install_prg_file
    for name,data in (('EMPTY',b''),('ONE',b'Q'),('LONG',LONG)):
        install(image,name,data,file_type=0x81)
    return bytes(image)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format',choices=('d64','d81'),default='d81')
    args=parser.parse_args()
    out=ROOT/'build/native-console/files'; out.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix=args.format+'-',dir=out))
    source=(ROOT/f'build/boot/udeks.{args.format}').read_bytes()
    apps={n:(ROOT/f'build/native-console/{n.lower()}/{n}.BIN').read_bytes()
          for n in (() if args.format=='d64' else ('FHOLD','FRIVAL'))}
    fixture=make_fixture(source,apps)
    disk=work/('test.'+args.format); disk.write_bytes(fixture)
    (work/('before.'+args.format)).write_bytes(fixture)
    text=(ROOT/'build/8502/udeks-8502.map').read_text()
    seg=map_segments(text)
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    storage=map_exports((ROOT/'build/storage/module.map').read_text())
    generations=storage['_udeks_storage_generations'][0]
    cleanup=storage['_udeks_storage_cleanup_error'][0]
    symbols={n:map_exports((ROOT/f'build/native-console/{n.lower()}/program.map').read_text()) for n in apps}
    port=choose_port(); records=[]
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',
         '1541' if args.format=='d64' else '1581'),log_path=work/'vice.log')

    def capture(tag,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),address,address+size-1,bank)])[0]
    def byte(address,bank='kernel'): return capture('byte-'+hex(address),address,1,bank)[0]
    def screen(tag='console'):
        cells=capture(tag,seg['LOWBSS'][0],1368)
        return '\n'.join(cells[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
    def wait(test,label,seconds=120):
        deadline=time.monotonic()+seconds
        while not test():
            if time.monotonic()>deadline: raise AssertionError((label,screen()))
            time.sleep(.05)
    def slot(task): return capture('task-'+str(task),slots+(task-1)*8,8)
    def prompt(): wait(lambda:slot(1)[1:3]==b'\4\2','shell prompt')
    def command(line,foreground=False,contains=None,status=None):
        prompt(); before=byte(0xf3d8)
        type_command(port,queue,line,time.monotonic()+120)
        wait(lambda:byte(0xf3d8)==(before+1)&255,'command consumed')
        if not foreground:
            prompt(); shown=screen()
            if contains is not None and contains not in shown: raise AssertionError((line,shown))
            if status is not None and byte(0xf17a)!=status: raise AssertionError((line,'status',byte(0xf17a),shown))
            records.append(dict(command=line,status=byte(0xf17a),console=shown))
            print('PASS',line,flush=True)
    def address(app,task,name):
        base=next(a[1] for a in ALLOCATIONS if a[0]==task)
        return base+symbols[app]['_'+name][0]-0x1000
    def private(app,task,name): return byte(address(app,task,name),'worker')
    def stage(app,task,name,value):
        # Foreground submission precedes disk loading: old slot RAM (including
        # a previous binary's relocation table) is NOT a new client's status.
        live=(app=='FHOLD' and value==2) or (app=='FRIVAL' and value==1)
        wait(lambda:private(app,task,name)==value and
             (not live or slot(task)[1:3]==b'\4\3'),name)
    def release(app,task,name): sp.write_blocks(port,[(address(app,task,name),b'\1')],'worker')
    def generation(task): return byte(generations+task,'worker')
    def retired(task,before,tag):
        wait(lambda:slot(task)[1]==0,'reaped')
        after=generation(task)
        if after!=(before+1)&255 or byte(cleanup,'worker'): raise AssertionError(('cleanup',task,before,after))
        records.append(dict(check=tag,task=task,before=before,after=after,cleanup=0))
        print('PASS',tag,flush=True)
    def guards(app,task,tag):
        _,base,limit,stack,_,_=next(a for a in ALLOCATIONS if a[0]==task)
        image=apps.get(app,(ROOT/f'build/native-console/{app.lower()}/{app}.BIN').read_bytes())
        if capture(tag+'-code',base,int.from_bytes(image[10:12],'little'),'worker')!=relocate_executable(image,base,limit-base)[16:]:
            raise AssertionError('code changed')
        for offset in (0,0xb0):
            if capture(tag+'-guard-'+str(offset),stack+offset,16,'worker')!=b'\xa5'*16: raise AssertionError('stack guard')
        capture(tag+'-state',base+int.from_bytes(image[10:12],'little'),int.from_bytes(image[12:14],'little'),'worker')
    def cancel():
        wait_keyboard_queue(port,queue,time.monotonic()+30)
        sp.write_kernel_blocks(port,[(queue,bytes((1,255,3,0))),(queue+64,b'\1\0\1')])
        wait_keyboard_queue(port,queue,time.monotonic()+30); prompt()
        if byte(0xf17a)!=130: raise AssertionError(('cancel status',byte(0xf17a)))

    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240); prompt()
        # No wall-clock/timing claim: accelerate routine disk loads. Keep
        # real-time execution for the live CAT/cancellation/concurrency checks.
        command('cat /hello',contains='HELLO UDEKS',status=0)
        command('cat /empty',status=0)
        command('cat /one',contains='Q',status=0)
        command('cat /nofile',contains='No such file or directory',status=1)
        command('cat /',contains='Is a directory',status=1)
        command('cat',contains='cat FILE',status=2)
        if apps:
            # Rival must already be loaded before the holder owns the only
            # stream. Its EXIT must not close the OTHER task's descriptor.
            command('frival &'); stage('FRIVAL',6,'rival_stage',1)
            rival_before=generation(6); owner_before=generation(4)
            command('fhold &'); stage('FHOLD',4,'file_stage',2)
            release('FRIVAL',6,'rival_release'); stage('FRIVAL',6,'rival_stage',2)
            retired(6,rival_before,'foreign-read-write-close-open-denied')
            guards('FRIVAL',6,'rival')
            release('FHOLD',4,'file_release'); stage('FHOLD',4,'file_stage',3)
            retired(4,owner_before,'leaked-read-exit'); guards('FHOLD',4,'holder')
            command('cat /hello',contains='HELLO UDEKS',status=0)
            for mode in ('exit','cancel'):
                before=generation(6)
                command('fhold write',True); stage('FHOLD',6,'file_stage',2)
                if mode=='exit':
                    release('FHOLD',6,'file_release'); prompt()
                    if byte(0xf17a)!=17: raise AssertionError('native exit status')
                else: cancel()
                retired(6,before,'leaked-write-'+mode); guards('FHOLD',6,'writer-'+mode)
                if mode=='exit':
                    command('fhold write',status=1)
                    if private('FHOLD',6,'file_error')!=17: raise AssertionError('exclusive create did not reject existing file')
                # CAT reads a binary stream too; inspect persisted bytes below.
                command('cp /native-data /saved-'+mode,status=0)
                command('rm /native-data',status=0)
            command('cat /hello',contains='HELLO UDEKS',status=0)

        command('xclock &'); wait(lambda:byte(0xf246)==1,'clock window')
        command('xwave &'); wait(lambda:byte(0xf246)==2,'wave window')
        sp.monitor_command(port,'warp off')
        before=generation(3)
        command('cat /long',True)
        wait(lambda:slot(3)[1:3]==b'\4\3','cat sleeps between file chunks')
        guards('CAT',3,'cat-live')
        cancel(); retired(3,before,'cat-read-cancel')
        # Built-ins update ush's private status, not the external completion
        # mailbox at $F17A. Check their visible result, not that stale byte.
        command('echo $?',contains='130')
        command('cat /hello',contains='HELLO UDEKS',status=0)
        # Clock faces update only once per minute. Prove execution via its
        # changing private SLEEP deadline while CAT still owns a live task,
        # not a face counter or the global timer (which could tick alone).
        waits=map_exports((ROOT/'build/8502/udeks-scheduler-overlay.map').read_text())
        deadline=waits['_udeks_task_wait_selector_private'][0]+3 # clock is task 4
        def clock_deadline(tag):
            raw=capture(tag,deadline,9)
            return raw[0]+256*raw[8]
        command('cat /long',True)
        wait(lambda:slot(3)[1:3]==b'\4\3','long CAT active')
        old_deadline=clock_deadline('clock-wait-before')
        wait(lambda:clock_deadline('clock-wait-after')!=old_deadline and slot(3)[1] in (2,3,4),
             'clock reslept while CAT active')
        new_deadline=clock_deadline('clock-wait-observed')
        records.append(dict(check='clock-progress-during-cat',before=old_deadline,after=new_deadline))
        prompt()
        if 'line 095 - native cat' not in screen() or byte(0xf17a): raise AssertionError('long CAT did not complete')
        records.append(dict(command='cat /long',status=0,console=screen('cat-complete-console')))
        guards('CAT',3,'cat-complete')
        if byte(0xf246)!=2 or byte(0xf11b): raise AssertionError('graphical peer/canary failure')
        command('xwave -q'); command('xclock -q')
        wait(lambda:byte(0xf246)==0,'windows closed')
        command('echo file-sdk-ok',contains='file-sdk-ok')
        capture('final-generations',generations,12,'worker')
        (work/'report.json').write_text(json.dumps(dict(format=args.format,
            source_disk_sha256=hashlib.sha256(source).hexdigest(),
            fixture_sha256=hashlib.sha256(fixture).hexdigest(),
            apps={n:hashlib.sha256(d).hexdigest() for n,d in apps.items()},checks=records),indent=2)+'\n')
    except Exception:
        print(screen('failure-console'),flush=True)
        capture('failure-tasks',slots,64)
        capture('failure-request',0xf359,38)
        capture('failure-generations',generations,12,'worker')
        for app,task,name in (('FHOLD',6,'file_stage'),('FHOLD',4,'file_stage'),('FRIVAL',6,'rival_stage')):
            if app in apps: capture('failure-'+app+'-'+str(task),address(app,task,name),5,'worker')
        raise
    finally:
        sp.terminate(proc,port); os.close(master)
    if apps:
        saved=files(disk.read_bytes()); before_files=files(fixture)
        for name,data in before_files.items():
            if saved.get(name)!=data: raise AssertionError(('existing file changed',name))
        if {n:d for n,d in saved.items() if n not in before_files}!={b'SAVED-EXIT':PAYLOAD,b'SAVED-CANCEL':PAYLOAD}:
            raise AssertionError('writer persistence')
    elif disk.read_bytes()!=fixture:
        raise AssertionError('read-only CAT changed the disk')
    (work/'disk-audit.json').write_text(json.dumps(dict(existing_files_unchanged=True,
        created={name:PAYLOAD.hex() for name in ('SAVED-EXIT','SAVED-CANCEL')} if apps else {},
        after_sha256=hashlib.sha256(disk.read_bytes()).hexdigest()),indent=2)+'\n')
    print('PASS native console files:',work,flush=True)


if __name__=='__main__': main()

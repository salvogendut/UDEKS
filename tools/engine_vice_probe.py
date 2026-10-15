#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold-boot engine exchanges and restart soak on VICE D71/D81."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import time
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from o65_to_udex import relocate_executable
from storage_shell_probe import sp, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port
from vice_capture import PROMPT_RE, parse_monitor_byte
from add_disk_apps import add_apps

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('d71', 'd81'), default='d81')
    parser.add_argument('--restart-cycles', type=int, default=12)
    parser.add_argument('--lifecycle', action='store_true')
    parser.add_argument('--bounds', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.restart_cycles <= 100:
        parser.error('restart cycles must be in 1..100')
    output = ROOT / 'build/engine/vice'
    output.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=args.format+'-', dir=output))
    source = ROOT / f'build/engine/demo/udeks-engine.{args.format}'
    base_original = source.read_bytes()
    disk = work / ('test.'+args.format)
    shutil.copyfile(source, disk)
    if args.lifecycle:
        disk.write_bytes(add_apps(disk.read_bytes(), [('ENGPEER.BIN',(ROOT/'build/engine/peer/ENGPEER.BIN').read_bytes())]))
    if args.bounds:
        disk.write_bytes(add_apps(disk.read_bytes(), [('ENGBOUND.BIN',(ROOT/'build/engine/bounds/ENGBOUND.BIN').read_bytes())]))
    original = disk.read_bytes()
    kernel = (ROOT/'build/8502/udeks-8502.map').read_text()
    exports = map_exports(kernel)
    console = map_segments(kernel)['LOWBSS'][0]
    ipc = exports['_udeks_ipc_state'][0]
    queue = keyboard_queue_address(kernel, (ROOT/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    maps = {app: map_exports((ROOT/f'build/engine/{app}/program.map').read_text()) for app in ('client','server')}
    images = {app: (ROOT/f'build/engine/{app}/{name}.BIN').read_bytes() for app,name in [('client','ENGTEST'),('server','ENGINE')]}
    if args.lifecycle:
        maps['peer']=map_exports((ROOT/'build/engine/peer/program.map').read_text())
        images['peer']=(ROOT/'build/engine/peer/ENGPEER.BIN').read_bytes()
    if args.bounds:
        maps['bounds']=map_exports((ROOT/'build/engine/bounds/program.map').read_text())
        images['bounds']=(ROOT/'build/engine/bounds/ENGBOUND.BIN').read_bytes()
    harness_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    shutil.copyfile(Path(__file__),work/'executed-engine-vice-probe.py')
    port = choose_port()
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type','1571' if args.format=='d71' else '1581'), log_path=work/'vice.log')
    records = []
    def read(tag, address, count=1, bank='kernel-flat'):
        return sp.capture_blocks(port, [(work/(tag+'.bin'),address,address+count-1,bank)])[0]
    def wait(test, label):
        deadline = time.monotonic()+180
        while not test():
            if proc.poll() is not None or time.monotonic()>deadline:
                raise AssertionError((label, work))
            time.sleep(.05)
    def prompt():
        wait(lambda: read('idle',0xf184)==b'\0' and read('root',slots+1,2)==b'\4\2','shell prompt')
    def command(line, foreground=False):
        prompt()
        before = read('commands',0xf3d8)[0]
        type_command(port,queue,line,time.monotonic()+180)
        wait(lambda: read('commands',0xf3d8)[0]==(before+1)%256,'command accepted')
        if not foreground: prompt()
        if read('canary',0xf11b)!=b'\0': raise AssertionError('task canary')
        print('PASS',line,flush=True)
    def address(app,field,task):
        base=0x2300 if task==3 else 0x8000
        return base+maps[app]['_engine_'+app+'_'+field][0]-0x1000
    def app(app, field, count=1, task=None):
        task = task or (3 if app=='client' else 5)
        return read(app+'-'+field+str(task),address(app,field,task),count,'worker')
    def guards(app,task=None):
        task = task or (3 if app=='client' else 5)
        base,limit,stack = (0x2300,0x3500,0x3400) if task==3 else (0x8000,0x9000,0x8f00)
        expected = relocate_executable(images[app],base,limit-base)[16:]
        if read(app+'-code',base,len(expected),'worker')!=expected: raise AssertionError('code changed')
        for offset in (0,176):
            if read(app+'-guard'+str(offset),stack+offset,16,'worker')!=b'\xa5'*16: raise AssertionError('stack guard')
    def exchange(line, wave=False):
        jobs = int.from_bytes(app('server','jobs',2),'little')
        command(line)
        wait(lambda: app('client','state')==b'\2','client completion')
        if app('client','error')!=b'\0' or read('exit',0xf17a)!=b'\0': raise AssertionError('client failed')
        if int.from_bytes(app('server','jobs',2),'little')!=jobs+1: raise AssertionError('worker jobs')
        if wave and (app('client','samples',8)!=bytes((250,0,6,9,14,19,23,25)) or app('client','result',2)!=b'\x32\0'):
            raise AssertionError('exact waveform')
        guards('client'); guards('server')
    def cancel(server_task,peer_app,peer_task,peer_state):
        # Read the pending exchange and enqueue ordinary Ctrl-C key events in
        # one paused monitor session. MMU mapping is restored before resuming.
        observed={}
        def inject():
            with socket.create_connection(('127.0.0.1',port),timeout=3) as connection:
                connection.settimeout(15)
                buffer=b''
                def run(command,marker=None):
                    nonlocal buffer
                    start=len(buffer)
                    connection.sendall(command.encode('ascii')+b'\n')
                    while True:
                        fresh=buffer[start:]
                        if fresh.endswith(b') ') and PROMPT_RE.search(fresh[-32:]) and (marker is None or marker in fresh):return fresh
                        chunk=connection.recv(4096)
                        if not chunk:raise RuntimeError('monitor closed')
                        buffer+=chunk
                def byte(where):
                    return parse_monitor_byte(run(f'm {where:04x} {where:04x}',f':{where:04x}'.encode()),where)
                live=byte(0xff00)
                queued=False
                try:
                    run('> ff04 00')
                    server_state=byte(address('server','state',server_task))
                    actual_peer_state=byte(address(peer_app,'state',peer_task))
                    run('> ff01 00')
                    # IPC state is under the I/O overlay; inspect physical
                    # bank-0 RAM, as capture_blocks(kernel-flat) does.
                    run('bank ram00')
                    owners=[byte(ipc),byte(ipc+1)]
                    run('bank cpu')
                    pending=server_state==2 and actual_peer_state==peer_state and server_task in owners and peer_task in owners
                    if pending and byte(queue+66)==0:
                        run(f'> {queue:04x} 01 ff 03 02')
                        run(f'> {queue+64:04x} 01 00 01')
                        queued=True
                        observed.update(server_state=server_state,peer_state=actual_peer_state,owners=owners,server_task=server_task,peer_task=peer_task)
                finally:
                    run('bank cpu')
                    run(f'> ff00 {live:02x}')
                    connection.sendall(b'x\n')
                return queued
        wait(inject,'pending exchange for Ctrl-C')
        prompt()
        if read('cancel-exit',0xf17a)!=b'\x82':raise AssertionError('parent CANCEL status')
        if read('canary',0xf11b)!=b'\0':raise AssertionError('cancellation canary')
        records.append({'check':'Ctrl-C-input-while-blocked','peer_app':peer_app,'exit':130,**observed})
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        command('engtest')
        if read('exit',0xf17a)!=b'\2': raise AssertionError('missing service errno')
        command('xclock &'); command('xdraw &')
        if args.lifecycle:
            sp.monitor_command(port,'warp off')
            command('engine &')
            wait(lambda: app('server','state')==b'\1','server ready')
            command('engpeer abandon')
            wait(lambda: app('server','state')==b'\2','orphaned STOP acknowledgment')
            command('engtest',True)
            cancel(5,'client',3,1)
            wait(lambda: read('client-reaped',slots+17)==b'\0','cancelled client reaped')
            owners=read('cancel-client-pool',ipc,8)
            if owners[:2].count(5)!=1 or any(t not in (0,5) for t in owners[:2]) or any(owners[6:8]):raise AssertionError('client cancellation cleanup')
            sp.monitor_command(port,'warp on')
            wait(lambda: app('server','state')==b'\1','server ACK timeout recovery')
            exchange('engtest',True)
            command('engtest --stop')
            wait(lambda: read('pool',ipc,2)==b'\0\0','client cancellation recovery cleanup')
            records.append({'check':'cancel-public-client-during-orphaned-STOP','exit':130,'recovered':True})
            sp.monitor_command(port,'warp off')
            command('engpeer &')
            wait(lambda: app('peer','state')==b'\1','waiting peer')
            command('engine',True)
            cancel(3,'peer',5,2)
            sp.monitor_command(port,'warp on')
            wait(lambda: app('peer','state')==b'\3','orphan peer completion')
            wait(lambda: read('pool',ipc,2)==b'\0\0','server cancellation cleanup')
            if app('peer','error')!=b'\0' or app('peer','stale')!=b'\x09' or any(read('queues',ipc+6,2)):raise AssertionError('stale server or cleanup')
            guards('server',3); guards('peer',5)
            records.append({'check':'cancel-public-server-during-STOP-ACK-wait','exit':130,'stale_send_errno':9})
        if args.bounds:
            command('engine &')
            wait(lambda: app('server','state')==b'\1','bounds server ready')
            command('engbound')
            wait(lambda: app('bounds','state',task=3)==b'\2','bounds completion')
            if app('bounds','error',task=3)!=b'\0' or int.from_bytes(app('bounds','checks',2,3),'little')!=104:raise AssertionError('bounds checks')
            if int.from_bytes(app('server','jobs',2),'little')!=97:raise AssertionError('invalid request executed worker')
            guards('bounds',3); guards('server')
            exchange('engtest',True)
            command('engtest --stop')
            wait(lambda: read('pool',ipc,2)==b'\0\0','bounds cleanup')
            records.append({'check':'raw-wire-bounds','checks':104,'exact_waves':96,'invalid_requests':7})
        previous = 0
        for cycle in range(args.restart_cycles):
            command('engine &')
            wait(lambda: app('server','state')==b'\1','server ready')
            handle = int.from_bytes(app('server','handle',2),'little')
            if handle<=previous: raise AssertionError('handle reused')
            exchange('engtest --nop'); exchange('engtest',True)
            command('engtest --stop')
            wait(lambda: app('server','state')==b'\4' and read('pool',ipc,2)==b'\0\0','stop cleanup')
            if app('client','state')!=b'\2' or read('pool-queues',ipc+6,2)!=b'\0\0': raise AssertionError('stop acknowledgment or queue leak')
            if read('windows',0xf246)!=b'\2': raise AssertionError('graphics lost')
            guards('client'); guards('server')
            records.append({'cycle':cycle+1,'handle':handle,'exact_wave':True,'clean_stop':True})
            previous = handle
        command('xdraw -q'); command('xclock -q'); command('engtest')
        if read('exit',0xf17a)!=b'\2' or read('windows',0xf246)!=b'\0': raise AssertionError('final availability or windows')
        read('console-final',console,0x558); read('ipc-final',ipc,62)
        if disk.read_bytes()!=original or source.read_bytes()!=base_original: raise AssertionError('disk modified')
        (work/'report.json').write_text(json.dumps({'format':args.format,'disk_sha256':hashlib.sha256(original).hexdigest(),'base_disk_sha256':hashlib.sha256(base_original).hexdigest(),'records':records,'physical_c128':False,'live_cancellation':args.lifecycle,'bounds':args.bounds,'harness_sha256':harness_sha,'program_sha256':{app:hashlib.sha256(data).hexdigest() for app,data in images.items()}},indent=2)+'\n')
        print('PASS engine VICE:',work,flush=True)
    finally:
        if sys.exc_info()[0] is not None and proc.poll() is None:
            try:
                read('failure-console',console,0x558)
                read('failure-slots',slots,64)
                read('failure-common',0xf110,0x2f0)
                read('failure-pool',ipc,62)
                (work/'partial-records.json').write_text(json.dumps(records,indent=2)+'\n')
            except (OSError,RuntimeError): pass
        sp.terminate(proc,port)
        os.close(master)

if __name__=='__main__': main()

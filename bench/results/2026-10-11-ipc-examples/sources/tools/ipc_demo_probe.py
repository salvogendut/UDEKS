#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold-boot public IPC examples through ordinary shell/disk/native SDK paths.

Keyboard events launch each program. A temporary pointer-getter patch exercises
window movement, and an acknowledged WM click exercises drawing. No IPC reply,
endpoint, task or application state is fabricated by the monitor.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_app_layout import ALLOCATIONS
from o65_to_udex import relocate_executable
from storage_shell_probe import sp,byte,keyboard_queue_address,type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port
from xcalc_probe import pointer_test_scratch
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format',choices=('d71','d81'),default='d81');args=parser.parse_args()
    out=ROOT/'build/ipc/demo-vice';out.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix=args.format+'-',dir=out))
    original=ROOT/f'build/ipc/demo/udeks-ipc.{args.format}'
    disk=work/('test.'+args.format);shutil.copyfile(original,disk)
    source=disk.read_bytes()
    kernel=(ROOT/'build/8502/udeks-8502.map').read_text();exports=map_exports(kernel);segments=map_segments(kernel)
    queue=keyboard_queue_address(kernel,(ROOT/'build/8502/keyboard.s').read_text())
    schedmap=(ROOT/'build/8502/udeks-scheduler-overlay.map').read_text()
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    wake=map_exports(schedmap)['_udeks_task_wait_selector_private'][0]
    state=exports['_udeks_ipc_state'][0]
    symbols={name:map_exports((ROOT/f'build/ipc/{name}/program.map').read_text()) for name in ('server','client')}
    images={name:(ROOT/f'build/ipc/{name}/{binname}.BIN').read_bytes() for name,binname in [('server','IPCSRV'),('client','IPCPING')]}
    drawmap=map_exports((ROOT/'build/user/native-draw/xdraw.map').read_text())
    wm=re.search(r'^window_manager\.o:\n((?:[ \t].*\n)+)',kernel,re.M)[1]
    click=segments['BSS'][0]+int(re.search(r'BSS\s+Offs=([0-9A-F]+)\s+Size=000004',wm)[1],16)
    scratch=pointer_test_scratch(kernel)
    records=[];patched=[];port=choose_port()
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type','1571' if args.format=='d71' else '1581'),log_path=work/'vice.log')
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
        records.append(dict(command=line,console=screen()));print('PASS',line,flush=True)
    def pool(tag='ipc-pool'):return capture(tag,state,62,'kernel-flat')
    def owners():return pool()[:2]
    def row(task):return next(r for r in ALLOCATIONS if r[0]==task)
    def address(app,task,name):return row(task)[1]+symbols[app]['_ipc_'+app+'_'+name][0]-0x1000
    def value(app,task,name,size=1):return capture(app+'-'+name+str(task),address(app,task,name),size,'worker')
    def number(app,task,name):return int.from_bytes(value(app,task,name,2),'little')
    def app_check(app,task,phase):
        if value(app,task,'state')!=bytes((phase,)) or value(app,task,'error')!=b'\0':
            raise AssertionError((app,value(app,task,'state'),value(app,task,'error')))
        _,base,limit,stack,_,_=row(task)
        code=relocate_executable(images[app],base,limit-base)[16:]
        if capture(app+'-code',base,len(code),'worker')!=code:raise AssertionError('code changed: '+app)
        for offset in (0,0xb0):
            if capture(app+'-guard'+str(offset),stack+offset,16,'worker')!=b'\xa5'*16:raise AssertionError('stack guard: '+app)
    def server():
        wait(lambda:sum(bool(x) for x in owners())==1,'server endpoint')
        task=next(t for t in owners() if t);app_check('server',task,1);return task
    def client_check(text,server_task,server_handle,stop=False):
        task=3;app_check('client',task,2)
        packet=value('client',task,'reply',16);count=value('client',task,'count')[0]
        expected=b'\4' if stop else b'\2'+text.upper().encode('ascii')
        # STOP overwrites the sent ACK in private storage after validation.
        if stop:
            if count!=1 or packet[0]!=5:raise AssertionError('shutdown handshake state')
        elif count!=len(expected) or packet[:count]!=expected:raise AssertionError(('reply',packet.hex(),text))
        if number('client',task,'peer')!=server_handle:raise AssertionError('peer handle changed')
        if not stop:
            if owners().count(server_task)!=1 or any(t not in (0,server_task) for t in owners()):raise AssertionError('client endpoint leaked')
            if any(pool()[6:8]):raise AssertionError('message remains queued')
            if 'reply: '+text.upper() not in screen():raise AssertionError('reply not shown')
        records.append(dict(check='shutdown' if stop else 'request-reply',text=text,authenticated_source=server_handle,reply_hex=expected.hex(),client_task=task))
    def pointer(x,y,buttons):
        if not patched:
            for name,length,offsets in (('x',10,((3,0),(6,1))),('y',4,((1,2),)),('buttons',4,((1,3),))):
                where=exports['_udeks_pointer_'+name][0];old=capture('pointer-'+name,where,length)
                expected={'x':b'\x08\x78\xad\xd8\xf1\xae\xd9\xf1\x28\x60','y':b'\xad\xda\xf1\x60','buttons':b'\xad\xdb\xf1\x60'}[name]
                if old!=expected:raise ValueError('pointer getter changed')
                patched.append((where,old));new=bytearray(old)
                for offset,relative in offsets:new[offset:offset+2]=(scratch+relative).to_bytes(2,'little')
                sp.write_kernel_blocks(port,[(where,new)])
        sp.write_kernel_blocks(port,[(scratch,(x+12).to_bytes(2,'little')+bytes((y+40,buttons)))])
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240);prompt()
        if owners()!=b'\0\0':raise AssertionError('IPC pool not empty at boot')
        command('ipcping hello');command('echo $?')
        if not screen().endswith('echo $?\n2\nUDEKS:~>') or owners()!=b'\0\0':raise AssertionError('missing endpoint error')
        command('xclock &');clock=byte(port,0xf247)
        command('xdraw &');draw=byte(port,0xf247)
        command('ipcsrv &');srv=server();handle=number('server',srv,'handle')
        # Run the first exchange in the background so the shell/input remain
        # active at the same time as all four native tasks.
        sp.monitor_command(port,'warp off')
        # Hold application work for the documented 60 ticks, not a monitor
        # semaphore. Observe actual native state before injecting input.
        command('ipcping Mixed-case &')
        wait(lambda:value('server',srv,'state')==b'\4' and value('client',3,'state')==b'\1','four-task request in progress')
        live=capture('four-task-slots',slots+16,32)
        if any(live[i*8+1] not in (2,3,4,5) for i in range(4)):
            raise AssertionError('four native tasks not live during request')
        records.append(dict(check='four-native-tasks-during-request',tasks=[3,4,5,6],server_work_ticks=60))
        # Verify drawing client still consumes an event with the server live.
        sp.wait_for_byte(port,click,0,time.monotonic()+90)
        sp.write_kernel_blocks(port,[(click,bytes((draw,10,0,25)))])
        sp.wait_for_byte(port,click,0,time.monotonic()+90)
        cell=0xc600+drawmap['_udeks_xdraw_cells'][0]-0x1000
        wait(lambda:capture('draw-cell',cell,24,'worker')==b'\1'+bytes(23),'drawing event')
        before=capture('clock-wake-before',wake+3,1)
        pointer(134,55,0);sp.wait_for_byte(port,0xf24d,0,time.monotonic()+90)
        pointer(134,55,1);sp.wait_for_byte(port,0xf248,clock,time.monotonic()+90)
        pointer(150,71,1);sp.wait_for_byte(port,0xf249,140,time.monotonic()+90)
        pointer(150,71,0);sp.wait_for_byte(port,0xf248,0,time.monotonic()+90)
        sp.write_kernel_blocks(port,patched);patched.clear()
        wait(lambda:capture('clock-wake-after',wake+3,1)!=before,'clock scheduled')
        wait(lambda:value('client',3,'state')==b'\2','background client completion')
        wait(lambda:byte(port,slots+17)==0,'background client reaped')
        client_check('Mixed-case',srv,handle)
        sp.monitor_command(port,'warp on')
        command('ipcping 1234567890abcde');client_check('1234567890abcde',srv,handle)
        command('echo $?')
        if not screen().endswith('echo $?\n0\nUDEKS:~>'):raise AssertionError('client exit status')
        command('ipcping 1234567890abcdef');command('echo $?')
        if not screen().endswith('echo $?\n2\nUDEKS:~>') or any(t not in (0,srv) for t in owners()):raise AssertionError('oversized message error')
        command('ipcping Again');client_check('Again',srv,handle)
        if number('server',srv,'count')!=3:raise AssertionError('server did not process three independent clients')
        if byte(port,0xf246)!=2:raise AssertionError('graphical peers lost')
        command('echo IPC and graphics alive')
        command('ipcping --stop');client_check('',srv,handle,True)
        wait(lambda:owners()==b'\0\0','shutdown endpoint cleanup')
        app_check('server',srv,3)
        command('ipcping hello');command('echo $?')
        if not screen().endswith('echo $?\n2\nUDEKS:~>'):raise AssertionError('stopped server error')
        # Name-independent discovery and fresh lifetime on reuse.
        command('ipcsrv demo &');srv=server();new_handle=number('server',srv,'handle')
        if new_handle==handle:raise AssertionError('server handle reused')
        command('ipcping demo Zebra');client_check('Zebra',srv,new_handle)
        command('ipcping demo --stop');client_check('',srv,new_handle,True)
        wait(lambda:owners()==b'\0\0','renamed shutdown cleanup')
        command('xdraw -q');command('xclock -q');command('echo IPC demo returned')
        if byte(port,0xf11b):raise AssertionError('task canary')
        if disk.read_bytes()!=source or original.read_bytes()!=source:raise AssertionError('demo disk modified')
        report=dict(format=args.format,scope=__doc__,disk_sha256=hashlib.sha256(source).hexdigest(),
            programs={name:hashlib.sha256(image).hexdigest() for name,image in images.items()},records=records,
            native_1986=False,physical_c128=False,public_sdk=True,independent_programs=True)
        (work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS IPC demo:',work,flush=True)
    finally:
        if patched:sp.write_kernel_blocks(port,patched)
        sp.terminate(proc,port);os.close(master)
if __name__=='__main__':main()

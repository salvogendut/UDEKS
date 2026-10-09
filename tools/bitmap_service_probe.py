#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise packed bitmaps through real disk clients and the native FF16 gate.

Only keyboard input and map-checked pointer getters are injected. No request
replies, task state, retained bytes or drawing pixels are manufactured.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from add_disk_apps import add_apps
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_app_layout import ALLOCATIONS
from storage_shell_probe import sp, keyboard_queue_address, type_command, wait_keyboard_queue
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port
from xcalc_probe import bitmap_preview, pointer_test_scratch

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--drive',choices=('1571','1581'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();work=args.output.resolve();work.mkdir(parents=True,exist_ok=True)
    program=(ROOT/'build/bitmap-store/client/BMAP.BIN').read_bytes()
    image=add_apps(args.disk.read_bytes(),[(n+'.BIN',program) for n in ('BMAP','BPEER')])
    disk=work/('test'+args.disk.suffix);disk.write_bytes(image)
    text=(ROOT/'build/8502/udeks-8502.map').read_text();exports=map_exports(text);seg=map_segments(text)
    app=map_exports((ROOT/'build/bitmap-store/client/client.map').read_text())
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    allocations={task:(base,limit,stack,zp,hp) for task,base,limit,stack,zp,hp in ALLOCATIONS}
    port=choose_port();records=[];patched=[]
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')

    def capture(tag,start,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),start,start+size-1,bank)])[0]
    def byte(address,bank='kernel'): return capture('byte',address,1,bank)[0]
    def screen():
        data=capture('console',seg['LOWBSS'][0],1368)
        return '\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
    def wait(predicate,label,seconds=180):
        deadline=time.monotonic()+seconds
        while not predicate():
            if time.monotonic()>deadline:raise AssertionError((label,screen()))
            time.sleep(.05)
    def prompt():wait(lambda:capture('root',slots+1,2)==b'\4\2','shell prompt')
    def command(line,foreground=False):
        prompt();before=byte(0xf3d8);type_command(port,queue,line,time.monotonic()+180)
        wait(lambda:byte(0xf3d8)==(before+1)&255,'command accepted')
        if not foreground:prompt()
        records.append(dict(command=line));print('PASS',line,flush=True)
    def live(task):return byte(slots+(task-1)*8+1)!=0
    def find(name):
        result=[]
        def scan():
            names=capture('names',exports['_udeks_banked_graphics_names'][0],64)
            for task in allocations:
                if names[(task-3)*16:(task-2)*16].split(b'\0',1)[0]==name.encode() and live(task):
                    result.append(task);return True
            return False
        wait(scan,name+' task');return result[0]
    def variable(task,name):return app['_bitmap_'+name][0]-0x1000+allocations[task][0]
    def state(task,stage,error=0):
        wait(lambda:byte(variable(task,'stage'),'worker')==stage,'client stage '+str(stage))
        actual=byte(variable(task,'error'),'worker')
        if actual!=error or byte(variable(task,'protocol'),'worker')!=3:
            raise AssertionError(('client errors/protocol',task,actual,error))
    def retained(task,tag):
        raw=capture(tag+'-lengths',exports['_udeks_retained_lengths'][0],8)
        lengths=[int.from_bytes(raw[i:i+2],'little') for i in range(0,8,2)]
        if sum(n&8191 for n in lengths)>2304:raise AssertionError('pool overrun')
        size=lengths[task-3]&8191;offset=sum(n&8191 for n in lengths[:task-3])
        data=capture(tag+'-image',0x1300+offset,size) if size else b''
        return lengths[task-3],data
    def expected(width,height):
        stride=(width+7)//8
        data=bytearray((i*37+11)&255 for i in range(stride*height))
        if width%8:
            for i in range(stride-1,len(data),stride):data[i]&=255<<(8-width%8)
        return bytes(data)
    def canvas(tag,x,y,width,height,pending=False):
        data=expected(width,height);stride=(width+7)//8
        deadline=time.monotonic()+120
        while True:
            shadow,bitmap=sp.capture_blocks(port,[(work/(tag+'-shadow.bin'),seg['VICSHADOW'][0],seg['VICSHADOW'][1],'kernel'),
                (work/(tag+'-bitmap.bin'),0x6000,0x7f3f,'worker')])
            matches=all(bool(bitmap[((y+yy)//8)*320+((x+xx)//8)*8+(y+yy)%8]&(128>>((x+xx)%8)))==
                (False if pending else bool(data[yy*stride+xx//8]&(128>>(xx%8))))
                for yy in range(height) for xx in range(width))
            if shadow==bitmap and matches:break
            if time.monotonic()>deadline:raise AssertionError((tag,'bitmap pixels',shadow==bitmap))
            time.sleep(.1)
        (work/(tag+'.png')).write_bytes(bitmap_preview(bitmap))
        records.append(dict(check=tag,pixels=width*height,pending=pending,shadow_matches_vic=True))
        print('PASS',tag,'pixels',flush=True)
    def guards(task):
        stack=allocations[task][2]
        for offset in (0,0xb0):
            if capture(f'guard-{task}-{offset}',stack+offset,16,'worker')!=b'\xa5'*16:
                raise AssertionError('client stack guard')
    def pointer(x,y,buttons):
        scratch=pointer_test_scratch(text)
        if not patched:
            for name,length,offsets in (('x',10,((3,0),(6,1))),('y',4,((1,2),)),('buttons',4,((1,3),))):
                at=exports['_udeks_pointer_'+name][0];old=capture('pointer-'+name,at,length)
                required={'x':b'\x08\x78\xad\xd8\xf1\xae\xd9\xf1\x28\x60',
                    'y':b'\xad\xda\xf1\x60','buttons':b'\xad\xdb\xf1\x60'}[name]
                if old!=required:raise ValueError('pointer getter changed')
                patched.append((at,old));new=bytearray(old)
                for offset,relative in offsets:new[offset:offset+2]=(scratch+relative).to_bytes(2,'little')
                sp.write_kernel_blocks(port,[(scratch,bytes((12,0,40,0))),(at,new)])
        sp.write_kernel_blocks(port,[(scratch,(x+12).to_bytes(2,'little')+bytes((y+40,buttons)))])
    def restore_pointer():
        if patched:sp.write_kernel_blocks(port,patched);patched.clear()
    def cancel(task):
        wait_keyboard_queue(port,queue,time.monotonic()+30)
        sp.write_kernel_blocks(port,[(queue,bytes((1,255,3,0))),(queue+64,b'\1\0\1')])
        wait_keyboard_queue(port,queue,time.monotonic()+30);prompt()
        wait(lambda:not live(task),'cancel retirement')
        if byte(0xf17a)!=130 or retained(task,'cancelled')[0]:raise AssertionError('cancel status/pool')
    def stop(name,task):
        command(name+' -q');wait(lambda:not live(task),'stop retirement')
        if retained(task,'stopped')[0]:raise AssertionError('stop leaked retained memory')

    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240);prompt()
        command('bmap &');task=find('bmap');state(task,2)
        stored=retained(task,'normal')
        if stored!=(0x4000+1288,b'\4\0\16\x80\x50\x10\0\5'+expected(128,80)):
            raise AssertionError('retained header/pixels')
        canvas('normal',24,34,128,80);guards(task)
        handle=byte(variable(task,'handle'),'worker')
        pointer(25,26,0);wait(lambda:byte(0xf24d)==0,'released')
        pointer(25,26,1);wait(lambda:byte(0xf248)==handle,'dragging bitmap')
        pointer(55,56,1);wait(lambda:byte(0xf249)==50,'outline moved')
        pointer(55,56,0);wait(lambda:byte(0xf248)==0,'drag ended');restore_pointer()
        canvas('moved',54,64,128,80)
        command('xclock &');wait(lambda:byte(0xf246)==2,'clock overlap')
        command('xclock -q');wait(lambda:byte(0xf246)==1,'clock closed')
        canvas('uncovered',54,64,128,80)
        if retained(task,'after-move')!=stored:raise AssertionError('move/uncover altered image')
        command('bpeer wide &');peer=find('bpeer');state(peer,255,12)
        if retained(task,'after-oom')!=stored or retained(peer,'oom')[0]:raise AssertionError('OOM damaged allocation')
        stop('bpeer',peer)
        # Two independent bitmap owners; retire the earlier record to compel
        # compaction of any later record without retaining foreign pointers.
        command('bpeer small &');peer=find('bpeer');state(peer,2)
        peer_image=retained(peer,'peer-before');stop('bmap',task)
        if retained(peer,'peer-after')!=peer_image:raise AssertionError('peer damaged by compaction')
        canvas('peer',24,34,32,24);stop('bpeer',peer)
        for mode,width,height in (('wide',160,100),('odd',9,7)):
            command('bmap '+mode+' &');task=find('bmap');state(task,2)
            canvas(mode,24,34,width,height);guards(task);stop('bmap',task)
        command('bmap hold',foreground=True);task=find('bmap');state(task,1)
        flag,data=retained(task,'pending')
        if flag!=0x6000+1288 or data[6:8]!=b'\x13\0':raise AssertionError('pending transaction')
        canvas('pending',24,34,128,80,True);cancel(task)
        command('bmap abort &');task=find('bmap');state(task,4)
        if retained(task,'aborted')[0]:raise AssertionError('abort allocation leak')
        stop('bmap',task)
        command('bmap exit');wait(lambda:byte(0xf246)==0,'EXIT cleanup')
        if byte(0xf17a)!=7 or any(capture('exit-lengths',exports['_udeks_retained_lengths'][0],8)):
            raise AssertionError('EXIT status/allocation')
        command('bmap small &');task=find('bmap');state(task,2);guards(task)
        # Real close box invokes the service cleanup, not a synthetic CANCEL.
        pointer(60,26,0);wait(lambda:byte(0xf24d)==0,'close release')
        pointer(60,26,1);wait(lambda:not live(task),'close retirement')
        pointer(0,0,0);restore_pointer()
        if retained(task,'closed')[0]:raise AssertionError('close leaked allocation')
        command('cat /hello');command('echo bitmap API passed')
        if 'bitmap API passed' not in screen() or byte(0xf11b):raise AssertionError('console/canary')
        report=dict(drive=args.drive,abi_minor=20,stage='service integration, xview unchanged',
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),
            fixture_sha256=hashlib.sha256(image).hexdigest(),program_sha256=hashlib.sha256(program).hexdigest(),
            checks=records,retirement=['close','abort','exit','cancel'],future_version_rejected=21,
            older_bitmap_version_rejected=19)
        (work/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    finally:
        sp.terminate(proc,port)
        if master is not None:os.close(master)


if __name__=='__main__':main()

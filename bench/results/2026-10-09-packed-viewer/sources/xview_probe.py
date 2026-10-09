#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify XVIEW on a disposable disk through the real native launch/file API.

Keyboard queue input and map-checked pointer getter hooks drive the normal
shell/WM paths; no task, file reply, image pixels or scheduler state is forged.
Pointer hooks test the WM, not a physical mouse. Owned VICE is always stopped.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from build_d71 import install_prg_file
import build_d81
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from o65_to_udex import relocate_executable
from png_to_cbm import parse, build
from storage_shell_probe import sp, keyboard_queue_address, type_command, wait_keyboard_queue
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port
from xcalc_probe import bitmap_preview, pointer_test_scratch

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--picture',type=Path,required=True)
    parser.add_argument('--second-picture',type=Path,required=True)
    parser.add_argument('--small-picture',type=Path,required=True,
                        help='picture whose packed allocation leaves room for clock + wave')
    parser.add_argument('--wide-picture',type=Path,required=True)
    parser.add_argument('--output',type=Path,help='new evidence directory')
    parser.add_argument('--drive',choices=('1571','1581'),required=True)
    args=parser.parse_args()
    w,h,rows=parse(args.picture.read_bytes())
    out=ROOT/'build/xview/probes'; out.mkdir(parents=True,exist_ok=True)
    work=args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix=args.drive+'-',dir=out))
    if args.output: work.mkdir(parents=True,exist_ok=False)
    print('Evidence:',work,flush=True)
    original=args.disk.read_bytes(); image=bytearray(original)
    for name,data in (('BAD.CBM',b'CBM\0\2'+bytes(7)),
                      ('TRAIL.CBM',build(b'\x80',1,1)+b'X'),
                      ('PAD.CBM',build(b'\x80',1,1)[:-1]+b'\x81'),
                      ('BIG.CBM',build(bytes(8000),320,200)),
                      ('TRUNC.CBM',build(b'\xff'*1280,128,80)[:-1]),
                      ('ODD.CBM',build(b'\xaa\x80'*7,9,7)),
                      ('DENSE.CBM',build(b'\xff'*816,128,51))):
        if args.drive=='1581': build_d81.install_file(image,name,data,file_type=0x81)
        else: install_prg_file(image,name,data,file_type=0x81,max_track=70)
    fixture=bytes(image); disk=work/('test'+args.disk.suffix); disk.write_bytes(fixture)
    text=(ROOT/'build/8502/udeks-8502.map').read_text()
    exports=map_exports(text); seg=map_segments(text)
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    app=map_exports((ROOT/'build/xview/xview.map').read_text())
    program=(ROOT/'build/xview/XVIEW.BIN').read_bytes()
    bases={3:0x2300,5:0x8000}
    def address(name,task=5): return app['_xview_'+name][0]-0x1000+bases[task]
    port=choose_port(); records=[]; patched=[]
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')
    def capture(tag,start,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),start,start+size-1,bank)])[0]
    def byte(at,bank='kernel'): return capture('byte',at,1,bank)[0]
    def screen(tag='console'):
        data=capture(tag,seg['LOWBSS'][0],1368)
        return '\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
    def wait(test,label,seconds=180):
        deadline=time.monotonic()+seconds
        while not test():
            if time.monotonic()>deadline: raise AssertionError((label,screen()))
            time.sleep(.05)
    def prompt(): wait(lambda:capture('shell',slots+1,2)==b'\4\2','shell prompt')
    def command(line,foreground=False,status=None,contains=None):
        prompt(); before=byte(0xf3d8)
        type_command(port,queue,line,time.monotonic()+180)
        wait(lambda:byte(0xf3d8)==(before+1)&255,'command consumed')
        if not foreground:
            prompt()
            if status is not None and byte(0xf17a)!=status: raise AssertionError((line,byte(0xf17a),screen()))
            if contains is not None and contains not in screen(): raise AssertionError((line,screen()))
        records.append(dict(command=line)); print('PASS',line,flush=True)
    def ready(task=5,windows=1):
        wait(lambda:byte(address('ready',task),'worker')==1 and byte(0xf246)==windows,'viewer ready')
    def cancel():
        wait_keyboard_queue(port,queue,time.monotonic()+30)
        sp.write_kernel_blocks(port,[(queue,bytes((1,255,3,0))),(queue+64,b'\1\0\1')])
        wait_keyboard_queue(port,queue,time.monotonic()+30); prompt()
        if byte(0xf17a)!=130: raise AssertionError('Ctrl+C status')
        wait(lambda:byte(0xf246)==0,'cancelled window retired')
    def canvas(tag,x,y,picture=None):
        pw,ph,pixels=(w,h,rows) if picture is None else parse(picture.read_bytes())
        deadline=time.monotonic()+120
        while True:
            shadow,bitmap=sp.capture_blocks(port,[(work/(tag+'-shadow.bin'),seg['VICSHADOW'][0],seg['VICSHADOW'][1],'kernel'),
                (work/(tag+'-bitmap.bin'),0x6000,0x7f3f,'worker')])
            matches=all(bool(bitmap[((y+yy)//8)*320+((x+xx)//8)*8+(y+yy)%8] & (128>>((x+xx)%8)))==bool(pixels[yy][xx])
                        for yy in range(ph) for xx in range(pw))
            if shadow==bitmap and matches: break
            if time.monotonic()>deadline: raise AssertionError((tag,'pixel comparison failed',shadow==bitmap))
            time.sleep(.1)
        (work/(tag+'.png')).write_bytes(bitmap_preview(bitmap))
        records.append(dict(check=tag,pixels=pw*ph,shadow_matches_vic=True))
        print('PASS',tag,'exact pixels',flush=True)
    def pointer(x,y,buttons):
        scratch=pointer_test_scratch(text)
        if not patched:
            for name,length,offsets in (('x',10,((3,0),(6,1))),('y',4,((1,2),)),('buttons',4,((1,3),))):
                at=exports['_udeks_pointer_'+name][0]; old=capture('pointer-'+name,at,length)
                expected={'x':b'\x08\x78\xad\xd8\xf1\xae\xd9\xf1\x28\x60','y':b'\xad\xda\xf1\x60','buttons':b'\xad\xdb\xf1\x60'}[name]
                if old!=expected: raise ValueError('pointer getter changed')
                patched.append((at,old)); new=bytearray(old)
                for offset,relative in offsets: new[offset:offset+2]=(scratch+relative).to_bytes(2,'little')
                sp.write_kernel_blocks(port,[(scratch,bytes((12,0,40,0))),(at,new)])
        sp.write_kernel_blocks(port,[(scratch,(x+12).to_bytes(2,'little')+bytes((y+40,buttons)))])
    def restore_pointer():
        if patched: sp.write_kernel_blocks(port,patched); patched.clear()
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240); prompt()
        command('xview',status=2,contains='xview FILE.CBM')
        command('xview /nofile.cbm',status=1,contains='No such file')
        for name in ('bad','trail','pad','trunc'):
            command('xview /'+name+'.cbm',status=1,contains='Invalid CBM picture')
            wait(lambda:byte(0xf246)==0,'malformed file window cleanup')
            if any(capture('error-lengths',exports['_udeks_retained_lengths'][0],8)):
                raise AssertionError('malformed file retained leak')
        for name in ('big',):
            command('xview /'+name+'.cbm',status=1,contains='Picture exceeds viewer limits')
        command('cat /hello',status=0,contains='HELLO UDEKS')
        filename='/'+args.picture.name.lower()
        command('xview '+filename+' &'); ready()
        canvas('initial',24,18)
        handle=byte(0xf247)
        command('cat /hello',status=0,contains='HELLO UDEKS')
        retained=capture('pool-before',0x1300,8+((w+7)//8)*h)
        if retained[8:]!=args.picture.read_bytes()[11:]: raise AssertionError('packed retained copy')
        # Another fitting task must fail gracefully on pool capacity, not
        # corrupt the first owner or strand the one filesystem stream.
        command('xview /'+args.wide_picture.name.lower(),status=1,contains='Not enough display memory')
        wait(lambda:byte(0xf246)==1,'OOM frame cleanup')
        canvas('oom-peer-intact',24,18)
        pointer(25,8,0); wait(lambda:byte(0xf24d)==0,'pointer release')
        pointer(25,8,1); wait(lambda:byte(0xf248)==handle,'drag started')
        pointer(55,38,1); wait(lambda:byte(0xf249)==50,'outline moved')
        pointer(55,38,0); wait(lambda:byte(0xf248)==0,'drag ended'); restore_pointer()
        canvas('dragged',54,48)
        command('xclock &'); wait(lambda:byte(0xf246)==2,'clock coexistence')
        command('xclock -q'); wait(lambda:byte(0xf246)==1,'clock closed')
        canvas('uncovered',54,48)
        if capture('pool-after',0x1300,len(retained))!=retained: raise AssertionError('retained pool changed')
        installed=relocate_executable(program,0x8000,0x1000)[16:]
        if capture('app-code',0x8000,len(installed),'worker')!=installed: raise AssertionError('app code changed')
        for offset in (0,0xb0):
            if capture('stack-'+str(offset),0x8f00+offset,16,'worker')!=b'\xa5'*16: raise AssertionError('stack guard')
        pointer(50+max(w+8,48)-8,38,0); wait(lambda:byte(0xf24d)==0,'release before close')
        pointer(50+max(w+8,48)-8,38,1); wait(lambda:byte(0xf246)==0,'close box')
        pointer(0,0,0); restore_pointer()
        command('cat /hello',status=0,contains='HELLO UDEKS')
        command('xview /'+args.wide_picture.name.lower()+' &'); ready()
        canvas('wide-picture',24,18,args.wide_picture)
        command('xview -q'); wait(lambda:byte(0xf246)==0,'wide viewer closed')
        for name,pic in (('odd',build(b'\xaa\x80'*7,9,7)),('dense',build(b'\xff'*816,128,51))):
            path=work/(name.upper()+'.CBM'); path.write_bytes(pic)
            command('xview /'+name+'.cbm &'); ready()
            canvas(name,24,18,path)
            command('xview -q'); wait(lambda:byte(0xf246)==0,'test viewer closed')
        command('xview /'+args.small_picture.name.lower()+' &'); ready()
        canvas('small-picture',24,18,args.small_picture)
        command('xclock &'); wait(lambda:byte(0xf246)==2,'clock coexistence')
        command('xwave &'); wait(lambda:byte(0xf246)==3,'three windows created')
        wave=map_exports((ROOT/'build/user/native-wave/xwave_native.map').read_text())
        wave_presents=wave['_native_wave_presents'][0]-0x1000+0x2300
        wait(lambda:byte(wave_presents,'worker')>0,'wave actually published its drawing')
        if byte(wave['_native_wave_failure'][0]-0x1000+0x2300,'worker'):
            raise AssertionError('wave failed')
        # Clock's retained image must be present too, not just its window frame.
        lengths=capture('three-retained-lengths',exports['_udeks_retained_lengths'][0],8)
        sizes=[int.from_bytes(lengths[n:n+2],'little')&0x1fff for n in range(0,8,2)]
        if sizes[0]!=1128 or not sizes[1] or not sizes[2] or sum(sizes)>2304:
            raise AssertionError(('three retained images',sizes))
        capture('three-app-tasks',slots,64)
        records.append(dict(check='viewer-clock-wave-fully-presented',retained_bytes=sizes))
        command('xwave -q'); wait(lambda:byte(0xf246)==2,'wave closed')
        command('xclock -q'); wait(lambda:byte(0xf246)==1,'clock closed')
        canvas('small-uncovered',24,18,args.small_picture)
        command('xview -q'); wait(lambda:byte(0xf246)==0,'small viewer closed')
        # A second launch of the same binary receives independent code, BSS,
        # UARG and window ownership. Move first aside; compare both pictures.
        command('xview '+filename+' &'); ready()
        first=byte(0xf247)
        pointer(25,8,0); wait(lambda:byte(0xf24d)==0,'release')
        pointer(25,8,1); wait(lambda:byte(0xf248)==first,'first viewer drag')
        pointer(185,8,1); wait(lambda:byte(0xf249)==180,'first moved aside')
        pointer(185,8,0); wait(lambda:byte(0xf248)==0,'first drop'); restore_pointer()
        canvas('first-aside',184,18)
        command('xview /'+args.second_picture.name.lower()+' &'); ready(3,2)
        second=byte(0xf247)
        if first==second: raise AssertionError('window ownership alias')
        canvas('second-picture',24,18,args.second_picture)
        canvas('two-pictures',184,18)
        capture('two-app-tasks',slots,64)
        for task,stack in ((3,0x3400),(5,0x8f00)):
            code=relocate_executable(program,bases[task],0x1200 if task==3 else 0x1000)[16:]
            if capture('code-'+str(task),bases[task],len(code),'worker')!=code:
                raise AssertionError('private relocated code')
            for off in (0,0xb0):
                if capture('guard-'+str(task)+'-'+str(off),stack+off,16,'worker')!=b'\xa5'*16:
                    raise AssertionError('private stack guard')
        command('xview '+filename+' &',contains='task slot busy')
        canvas('after-rejected-third',24,18,args.second_picture)
        sw,_,_=parse(args.second_picture.read_bytes())
        pointer(20+max(sw+8,48)-8,8,0); wait(lambda:byte(0xf24d)==0,'release')
        pointer(20+max(sw+8,48)-8,8,1); wait(lambda:byte(0xf246)==1,'second closed')
        pointer(0,0,0); restore_pointer(); canvas('first-survives',184,18)
        command('xview /'+args.second_picture.name.lower(),foreground=True); ready(3,2)
        wait_keyboard_queue(port,queue,time.monotonic()+30)
        sp.write_kernel_blocks(port,[(queue,bytes((1,255,3,0))),(queue+64,b'\1\0\1')])
        wait_keyboard_queue(port,queue,time.monotonic()+30); prompt()
        if byte(0xf17a)!=130: raise AssertionError('second viewer Ctrl+C status')
        wait(lambda:byte(0xf246)==1,'only foreground viewer cancelled')
        canvas('background-survives-ctrl-c',184,18)
        command('xview -q'); wait(lambda:byte(0xf246)==0,'remaining viewer closed')
        records.append(dict(check='two-independent-viewers-close-cancel-reuse',passed=True))
        command('xview '+filename,foreground=True); ready(); cancel()
        command('cat /hello',status=0,contains='HELLO UDEKS')
        sp.monitor_command(port,'warp off')
        command('xview '+filename,foreground=True)
        def uploading():
            size=int.from_bytes(capture('upload-progress',address('uploaded'),2,'worker'),'little')
            return byte(slots+33) in (2,3,4) and byte(address('ready'),'worker')==0 and 19<=size<((w+7)//8)*h
        wait(uploading,'actual mid-upload cancellation')
        cancel()
        command('cat /hello',status=0,contains='HELLO UDEKS')
        command('xview '+filename,foreground=True); wait(uploading,'mid-upload close')
        pointer(20+max(w+8,48)-8,8,0); wait(lambda:byte(0xf24d)==0,'release before pending close')
        pointer(20+max(w+8,48)-8,8,1); wait(lambda:byte(0xf246)==0,'pending frame closed')
        pointer(0,0,0); restore_pointer(); prompt()
        if byte(0xf17a)!=0: raise AssertionError(('pending close status',screen()))
        if any(capture('final-lengths',exports['_udeks_retained_lengths'][0],8)):
            raise AssertionError('pending close retained leak')
        command('cat /hello',status=0,contains='HELLO UDEKS')
        if byte(0xf11b): raise AssertionError('kernel canary')
        records.append(dict(check='pending-close-cancel-stream-reuse-and-guards',passed=True))
        (work/'report.json').write_text(json.dumps(dict(drive=args.drive,
            source_sha256=hashlib.sha256(original).hexdigest(),fixture_sha256=hashlib.sha256(fixture).hexdigest(),
            app_sha256=hashlib.sha256(program).hexdigest(),checks=records),indent=2)+'\n')
    except Exception:
        print(screen('failure-console'),flush=True)
        capture('failure-task',slots,64); capture('failure-request',0xf359,38)
        raise
    finally:
        try: restore_pointer()
        finally: sp.terminate(proc,port); os.close(master)
    if disk.read_bytes()!=fixture or args.disk.read_bytes()!=original: raise AssertionError('viewer wrote to disk')
    print('PASS XVIEW:',work,flush=True)


if __name__=='__main__': main()

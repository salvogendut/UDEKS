#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold-boot REU-backed bitmaps through unmodified disk apps and public requests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from png_to_cbm import parse
from storage_shell_probe import sp, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port
from xcalc_probe import bitmap_preview

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--disk',type=Path,required=True)
    p.add_argument('--picture',type=Path,required=True)
    p.add_argument('--second-picture',type=Path)
    p.add_argument('--reu',type=int,choices=(0,128,256,512,1024),default=512)
    p.add_argument('--output',type=Path)
    p.add_argument('--pixel-timeout',type=int,default=100)
    args=p.parse_args()
    second=args.second_picture or args.picture
    base=ROOT/'build/reu-graphics';base.mkdir(parents=True,exist_ok=True)
    out=args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix='vice-',dir=base))
    if args.output:out.mkdir(parents=True,exist_ok=False)
    original=args.disk.read_bytes();disk=out/args.disk.name;shutil.copyfile(args.disk,disk)
    text=(ROOT/'build/8502/udeks-8502.map').read_text();seg=map_segments(text);sym=map_exports(text)
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    port=choose_port();checks=[]
    if args.reu:
        (out/'reu.img').write_bytes(bytes([0xa5])*(args.reu*1024))
    extra=('-reu','-reusize',str(args.reu),'-reuimage',str(out/'reu.img'),'-reuimagerw') if args.reu else ('+reu',)
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type','1581',*extra),log_path=out/'vice.log')
    def capture(tag,at,size,bank='kernel'):
        return sp.capture_blocks(port,[(out/(tag+'.bin'),at,at+size-1,bank)])[0]
    def byte(at,bank='kernel'):return capture('byte',at,1,bank)[0]
    def screen():
        raw=capture('console',seg['LOWBSS'][0],1368)
        return '\n'.join(raw[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
    def wait(test,label,seconds=100):
        deadline=time.monotonic()+seconds
        while not test():
            if time.monotonic()>deadline:raise AssertionError((label,screen()))
            time.sleep(.1)
    def prompt():wait(lambda:capture('shell',slots+1,2)==b'\4\2','shell prompt')
    def command(line):
        prompt();old=byte(0xf3d8);type_command(port,queue,line,time.monotonic()+100)
        wait(lambda:byte(0xf3d8)==(old+1)&255,'command consumed: '+line);prompt()
        checks.append({'command':line});print('PASS',line,flush=True)
    def lengths():
        data=capture('lengths',sym['_udeks_retained_lengths'][0],8)
        return [int.from_bytes(data[i:i+2],'little') for i in range(0,8,2)]
    def state():return capture('store',sym['_udeks_reu_store'][0],39,'kernel-flat')
    def image(tag,picture=None):
        w,h,rows=parse((picture or args.picture).read_bytes())
        def matches():
            shadow,bitmap=sp.capture_blocks(port,[(out/(tag+'-shadow.bin'),seg['VICSHADOW'][0],seg['VICSHADOW'][1],'kernel'),
                (out/(tag+'-bitmap.bin'),0x6000,0x7f3f,'worker')])
            if shadow!=bitmap:return False
            return all(bool(bitmap[((18+y)//8)*320+((24+x)//8)*8+(18+y)%8] & (128>>((24+x)%8)))==bool(rows[y][x])
                       for y in range(h) for x in range(w))
        wait(matches,tag+' exact pixels',args.pixel_timeout)
        (out/(tag+'.png')).write_bytes(bitmap_preview((out/(tag+'-bitmap.bin')).read_bytes()[2:]))
        checks.append({'pixels':w*h,'image':tag});print('PASS',tag,'exact pixels',flush=True)
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+100);prompt()
        code=capture('installed-code',0xd000,seg['BITMAPCODE'][2],'kernel-flat')
        expected=(ROOT/'build/8502/bitmap-hidden-sealed.bin').read_bytes()
        if code!=expected[:len(code)]:raise AssertionError('hidden code differs from linked delivery')
        if state()!=bytes(38)+bytes([bool(args.reu)]):raise AssertionError('initial storage state')
        before=capture('pointer-count',0xf1e2,2)
        backup=capture('bootfs-backup',0x4000,256,'worker')
        command('xview /'+args.picture.name.lower()+' &')
        wait(lambda:byte(0xf246)==1,'viewer window')
        image('initial')
        guards=capture('buffer-low-guard',0x417f,1,'worker')+capture('buffer-high-guard',0x419e,2,'worker')
        expected_size=8 if args.reu else len(args.picture.read_bytes())-11+8
        if sum(v&8191 for v in lengths())!=expected_size:raise AssertionError('retained allocation size')
        first=state()
        if args.reu:
            if first[0:2]!=b'\3\0' or first[8]!=2 or int.from_bytes(first[4:6],'little')!=2000:raise AssertionError('owner 3 committed record')
            command('xclock &');wait(lambda:byte(0xf246)==2,'clock coexistence')
            command('xwave &');wait(lambda:byte(0xf246)==3,'wave coexistence')
            wait(lambda:sum(bool(v&8191) for v in lengths())==3,'three retained drawings')
            checks.append({'coexistence':'CLOCK160 + clock + wave','retained_lengths':lengths()})
            command('echo REU desktop alive')
            if 'REU desktop alive' not in screen():raise AssertionError('console while REU graphics live')
            command('xwave -q');wait(lambda:byte(0xf246)==2,'wave closed')
            # Wave uses the joined allocation: CAT needs that task capacity,
            # even with ample REU bitmap storage. No extra slots are claimed.
            command('cat /hello')
            if 'HELLO UDEKS' not in screen():raise AssertionError('disk read while viewer and clock live')
            command('xclock -q');wait(lambda:byte(0xf246)==1,'clock closed')
            image('uncovered')
            if state()!=first:raise AssertionError('repaint changed storage ownership/progress')
            # Another image uses a distinct REU extent and large code slot.
            command('xview /'+second.name.lower()+' &')
            wait(lambda:byte(0xf246)==2 and sum(v&8191 for v in lengths())==16,'two large retained objects')
            wait(lambda:state()[8]==2 and state()[17]==2,'both uploads committed')
            image('two-large',second)
            checks.append({'coexistence':'two independent bitmap objects',
                'pictures':[args.picture.name,second.name],'store':state().hex()})
        else:
            command('xclock &')
            # A clock cannot publish 344 bytes alongside the 2008-byte stock
            # bitmap. It exits and retires its temporary window on rejection.
            command('cat /hello')
            wait(lambda:byte(0xf246)==1,'stock clock admission cleanup')
            if sum(v&8191 for v in lengths())>2304:raise AssertionError('stock pool overflow')
            image('stock-peer-intact')
        if args.reu:
            command('xview -q');wait(lambda:byte(0xf246)==1,'one independent viewer closed')
            image('peer-after-close')
        command('xview -q');wait(lambda:byte(0xf246)==0,'viewer cleanup')
        if any(lengths()) or any(state()[:36]):raise AssertionError('cleanup leaked RAM or REU ownership')
        command('xview /'+args.picture.name.lower()+' &');image('reuse')
        command('xview -q');wait(lambda:byte(0xf246)==0,'reuse cleanup')
        if any(lengths()) or any(state()[:36]):raise AssertionError('reuse cleanup leaked ownership')
        command('cat /hello')
        if 'HELLO UDEKS' not in screen():raise AssertionError('disk service not restored')
        if capture('pointer-after',0xf1e2,2)==before:raise AssertionError('pointer IRQ stopped')
        if capture('final-low-guard',0x417f,1,'worker')+capture('final-high-guard',0x419e,2,'worker')!=guards:
            raise AssertionError('DMA buffer overrun')
        if capture('final-bootfs',0xf400,256)!=backup or capture('final-backup',0x4000,256,'worker')!=backup:
            raise AssertionError('borrowed common page or immutable backup damaged')
        if capture('final-code',0xd000,len(code),'kernel-flat')!=code:raise AssertionError('hidden code corrupted')
        if byte(0xf11b):raise AssertionError('kernel canary')
    except Exception:
        print(screen(),flush=True)
        state();lengths();capture('dma-request',sym['_udeks_reu_request'][0],9)
        capture('failure-request',0xf359,38);capture('failure-hidden',0xd000,4096,'kernel-flat')
        raise
    finally:
        sp.terminate(proc,port);os.close(master)
    if disk.read_bytes()!=original or args.disk.read_bytes()!=original:raise AssertionError('probe wrote disk')
    if args.reu:
        actual=(out/'reu.img').read_bytes();expected=bytearray([0xa5])*len(actual)
        for at,picture in ((0,args.picture),(8192,second)):
            pixels=picture.read_bytes()[11:];expected[at:at+len(pixels)]=pixels
        if actual!=expected:raise AssertionError('REU object bytes or unowned expansion bytes differ')
        checks.append({'reu_extents_exact':2,'unowned_expansion_bytes_untouched':True})
    sources=('Makefile','mk/reu_graphics.mk','cfg/8502-bootstrap.cfg','cfg/8502-panic-probe.cfg',
        'src/services/window/reu_runtime.s','src/services/window/reu_bitmap.c',
        'src/services/window/retained_bitmap.c','src/services/window/retained_bitmap_paint.s',
        'src/services/window/retained_pool.s','src/services/window/retained_paths.c',
        'src/services/memory/reu.s','src/services/memory/reu_capacity.c','src/services/memory/reu_store.c',
        'src/scheduler/task_context.s','src/scheduler/task_yield_handler.s',
        'tools/reu_graphics_probe.py','tools/reu_graphics_layout.py','tools/shadow_boot_probe.py')
    (out/'report.json').write_text(json.dumps({'reu_kib':args.reu,'checks':checks,
        'disk_sha256':hashlib.sha256(original).hexdigest(),
        'pictures':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.picture,second)},
        'emulator':subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True),
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources}},indent=2)+'\n')
    print('PASS live REU bitmap:',out,flush=True)


if __name__=='__main__':main()

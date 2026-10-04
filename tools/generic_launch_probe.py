#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Launch OS-unknown filenames through ush; qualify automatic slots and reuse.

WM events are injected, not a physical mouse test. No loader/poll hooks are
used: every load, rejection and shutdown goes through ordinary shell input.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
from build_d71 import install_prg_file
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, monitor_command
from xcalc_probe import bitmap_preview, pointer_test_scratch

ROOT=Path(__file__).resolve().parents[1]

def fixtures(program):
    files={name:program for name in ('hello','second','extra')}
    for name,offset,value in (('badmagic',0,0),('badpatch',len(program)-1,255)):
        bad=bytearray(program);bad[offset]=value;files[name]=bytes(bad)
    # Same executable with zero-filled image padding (also covering its old
    # BSS addresses); patches retain their offsets. Fits task 3 but not task 4.
    end=16+int.from_bytes(program[10:12],'little')
    large=bytearray(program[:end]+bytes(2500)+program[end:])
    large[10:12]=(end-16+2500).to_bytes(2,'little')
    files['large']=bytes(large)
    return files

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive',choices=('1541','1571'),default='1541')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    work=args.output.resolve();work.mkdir(parents=True,exist_ok=True)
    program=(ROOT/'build/generic-apps/example/HELLO.BIN').read_bytes()
    disk_image=bytearray(args.disk.read_bytes())
    for name,data in fixtures(program).items():
        install_prg_file(disk_image,name.upper()+'.BIN',data,file_type=0x81)
    disk=work/('test'+args.disk.suffix);disk.write_bytes(disk_image)
    text=(ROOT/'build/8502/udeks-8502.map').read_text()
    segments=map_segments(text);exports=map_exports(text)
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    names=exports['_udeks_banked_graphics_names'][0]
    module=re.search(r'^window_manager\.o:\n((?:[ \t].*\n)+)',text,re.M)[1]
    click=segments['BSS'][0]+int(re.search(r'BSS\s+Offs=([0-9A-F]+)\s+Size=000004',module)[1],16)
    click_symbol=map_exports((ROOT/'build/generic-apps/example/xhello.map').read_text())['_hello_clicks'][0]
    pointer_scratch=pointer_test_scratch(text)
    port=choose_port()
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')
    records=[];original_getters=[]
    def capture(name,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(name+'.bin'),address,address+size-1,bank)])[0]
    def console():
        cells=capture('console',segments['LOWBSS'][0],0x558)
        return '\n'.join(cells[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,21*65,65))
    def command(line,expected=None,windows=None):
        deadline=time.monotonic()+150
        sp.wait_for_byte(port,slots+1,4,deadline)
        before=byte(port,0xf3d8)
        type_command(port,queue,line,deadline)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline)
        if windows is not None: sp.wait_for_byte(port,0xf246,windows,deadline)
        while True:
            output=console()
            if expected is None or expected in output: break
            if time.monotonic()>deadline: raise AssertionError((line,output))
            time.sleep(.1)
        records.append(dict(command=line,console=output))
        print('PASS',line,flush=True)
    def check_names(expected):
        actual=capture('names',names,32)
        for index,name in expected.items():
            if actual[index*16:index*16+16]!=name.encode().ljust(16,b'\0'):
                raise AssertionError(('instance name',index,actual))
    def protected(tag):
        return [capture(tag+'-code'+str(i),base,int.from_bytes(program[10:12],'little'),'worker')
                for i,base in enumerate((0x2300,0x3500))]+[capture(tag+'-retained',0xc600,2560,'worker')]
    def pointer(x,y,buttons):
        if not original_getters:
            for name,length,offsets in (('x',10,((3,0),(6,1))),('y',4,((1,2),)),('buttons',4,((1,3),))):
                address=exports['_udeks_pointer_'+name][0]
                original=capture('pointer-'+name,address,length)
                expected={'x':b'\x08\x78\xad\xd8\xf1\xae\xd9\xf1\x28\x60',
                    'y':b'\xad\xda\xf1\x60','buttons':b'\xad\xdb\xf1\x60'}[name]
                if original!=expected: raise ValueError('pointer getter changed')
                original_getters.append((address,original));patched=bytearray(original)
                for offset,relative in offsets:
                    patched[offset:offset+2]=(pointer_scratch+relative).to_bytes(2,'little')
                sp.write_kernel_blocks(port,[(pointer_scratch,bytes((12,0,40,0))),(address,patched)])
        sp.write_kernel_blocks(port,[(pointer_scratch,(x+12).to_bytes(2,'little')+bytes((y+40,buttons)))])
    def canvas(name):
        deadline=time.monotonic()+60
        while True:
            shadow,bitmap=sp.capture_blocks(port,[(work/(name+'-shadow.bin'),0xa1e0,0xc11f,'kernel'),
                                                (work/(name+'-bitmap.bin'),0x6000,0x7f3f,'worker')])
            if shadow==bitmap: break
            if time.monotonic()>deadline: raise AssertionError('bitmap differs from shadow')
            time.sleep(.1)
        (work/(name+'.png')).write_bytes(bitmap_preview(bitmap))
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        command('hello &',windows=1);check_names({0:'hello'})
        for line,message in (('badmagic &','loader error'),('badpatch &','loader error'),
                             ('absent &','Unknown command: absent'),('large &','task slot busy')):
            before=capture('peer-before',0x2300,0x1200,'worker')
            command(line,message)
            # BSS/counters can change; code and initialized image cannot here.
            size=int.from_bytes(program[10:12],'little')
            if capture('peer-after',0x2300,size,'worker')!=before[:size]: raise AssertionError('rejection damaged peer')
        command('second &',windows=2);check_names({0:'hello',1:'second'})
        sp.wait_for_byte(port,0xf083,25,time.monotonic()+60)
        second_handle=byte(port,0xf247)
        before=protected('before-full')
        command('extra &','task slot busy')
        command('xcalc -q','xcalc: not ready')
        command('xdraw -q','xdraw: not ready')
        if protected('after-full')!=before: raise AssertionError('full/legacy rejection damaged instances')
        sp.wait_for_byte(port,0xf246,2,time.monotonic()+60)
        command('cowsay generic alive','generic alive')
        sp.write_kernel_blocks(port,[(click,bytes((second_handle,20,0,28)))])
        deadline=time.monotonic()+60
        while capture('second-clicks',0x3500+click_symbol-0x1000,1,'worker')!=b'\1':
            if time.monotonic()>deadline: raise AssertionError('second client did not consume click')
            time.sleep(.1)
        if capture('first-clicks',0x2300+click_symbol-0x1000,1,'worker')!=b'\0':
            raise AssertionError('click crossed task ownership')
        pointer(60,45,0);sp.wait_for_byte(port,0xf24d,0,time.monotonic()+60)
        pointer(60,45,1);sp.wait_for_byte(port,0xf248,second_handle,time.monotonic()+60)
        pointer(175,90,1);sp.wait_for_byte(port,0xf249,165,time.monotonic()+60)
        pointer(175,90,0);sp.wait_for_byte(port,0xf248,0,time.monotonic()+60)
        canvas('two-generic-windows')
        monitor_command(port,f'screenshot "{work/"console.bmp"}" 0')
        # Close the moved second instance and reuse the now-free task 4.
        pointer(257,91,1);sp.wait_for_byte(port,0xf246,1,time.monotonic()+60)
        pointer(257,91,0)
        sp.write_kernel_blocks(port,original_getters);original_getters.clear()
        sp.wait_for_byte(port,slots+25,0,time.monotonic()+60)
        command('extra &',windows=2);check_names({0:'hello',1:'extra'})
        if capture('reused-clicks',0x3500+click_symbol-0x1000,1,'worker')!=b'\0':
            raise AssertionError('reload retained old BSS')
        command('xinit -q','VIC-II graphics stopped',windows=0)
        for offset in (17,25): sp.wait_for_byte(port,slots+offset,0,time.monotonic()+60)
        command('large &',windows=1);check_names({0:'large'})
        command('second &',windows=2);check_names({0:'large',1:'second'})
        command('xinit -q','VIC-II graphics stopped',windows=0)
        command('echo slots reusable','slots reusable')
        if byte(port,0xf11b): raise AssertionError('task canary failure')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive,
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),
            fixture_sha256=hashlib.sha256(disk_image).hexdigest(),
            program_sha256=hashlib.sha256(program).hexdigest(),
            unknown_names=True,automatic_slots=True,legacy_stop_safe=True,
            independent_input=True,drag_close_reuse=True,records=records),indent=2)+'\n')
    finally:
        sp.terminate(proc,port);os.close(master)

if __name__=='__main__':main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the native-clock migration candidate through ordinary shell input.

VICE keyboard/WM injection, not native mouse or physical-hardware evidence.
The production XCLOCK/XWAVE programs are left on the candidate disk unchanged.
"""
import argparse
import hashlib
import json
import math
import os
import socket
from pathlib import Path
import time
from add_disk_apps import add_apps
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from o65_to_udex import relocate_executable
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, receive_prompts, quote_monitor_path
from xcalc_probe import bitmap_preview, pointer_test_scratch

ROOT=Path(__file__).resolve().parents[1]


def clock_commands(hour,minute,width=72,height=88):
    """Independent geometric oracle for the 43 retained generic commands."""
    center_x=width//2; center_y=16+(height-40)//2
    radius=min((height-40)//2,(width-8)//2)
    def point(position,radius):
        sx=round(64*math.sin(position*math.pi/30))
        cy=round(64*math.cos(position*math.pi/30))
        return (center_x+int(sx*radius/64),center_y-int(cy*radius/64))
    commands=[]
    def line(start,end): commands.extend((1,*start,*end,0,0,0))
    position=0
    for i in range(24):
        next_position=(position+(3 if i&1 else 2))%60
        line(point(position,radius),point(next_position,radius)); position=next_position
    for position in range(0,60,5): line(point(position,radius),point(position,radius-radius//8))
    line((center_x,center_y),point((hour%12)*5+minute//12,radius//2))
    line((center_x,center_y),point(minute,radius*3//4))
    glyphs=((7,5,5,5,7),(2,6,2,2,7),(7,1,7,4,7),(7,1,7,1,7),(5,5,7,1,1),
            (7,4,7,1,7),(7,4,7,5,7),(7,1,1,1,1),(7,5,7,5,7),(7,5,7,1,7),(0,2,0,2,0))
    for i,digit in enumerate((hour//10,hour%10,10,minute//10,minute%10)):
        commands.extend((2,center_x-19+8*i,height-16,*glyphs[digit]))
    return bytes(commands)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--drive',choices=('1541','1571','1581'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    work=args.output.resolve(); work.mkdir(parents=True,exist_ok=True)
    program=(ROOT/'build/native-clients/clock/NCLOCK.BIN').read_bytes()
    if len(program)>0xb00 or sum(int.from_bytes(program[n:n+2],'little') for n in (10,12))>0xb00:
        raise ValueError('native clock must fit BOTH image/BSS and file bounds of the smaller slot')
    image=add_apps(args.disk.read_bytes(),[('NCLOCK.BIN',program),('CLOCK2.BIN',program)])
    disk=work/('native-clock'+args.disk.suffix); disk.write_bytes(image)
    kernel_map=(ROOT/'build/8502/udeks-8502.map').read_text()
    segments=map_segments(kernel_map); exports=map_exports(kernel_map)
    app_symbols=map_exports((ROOT/'build/native-clients/clock/xclock_native.map').read_text())
    queue=keyboard_queue_address(kernel_map,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    scratch=pointer_test_scratch(kernel_map)
    port=choose_port()
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')
    records=[]; pointer_original=[]
    def capture(name,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(name+'.bin'),address,address+size-1,bank)])[0]
    def panel(tag,rows):
        """Read actual logical VDC RAM, not the console's backing buffer."""
        path=work/(tag+'-panel.bin'); deadline=time.monotonic()+60
        while True:
            path.unlink(missing_ok=True)
            with socket.create_connection(('127.0.0.1',port),timeout=3) as connection:
                connection.settimeout(10)
                try:
                    # The first command enters the monitor: initial + reply prompts.
                    connection.sendall(b'bank vdc\n'); receive_prompts(connection,2)
                    connection.sendall(('save '+quote_monitor_path(path)+' 0 0000 0fff\n').encode())
                    reply=receive_prompts(connection)
                    if b'Saving' not in reply: raise RuntimeError(reply)
                finally:
                    connection.sendall(b'bank cpu\n'); receive_prompts(connection)
                    connection.sendall(b'x\n')
            data=path.read_bytes()[2:]
            if len(data)!=4096: raise AssertionError('short VDC capture')
            valid=True
            for row,text in rows.items():
                expected=bytes(ord(c.upper())&31 if c.isalpha() else ord(c)
                               for c in text.ljust(9))
                address=0x04b2+row*80
                valid &= data[address:address+9]==expected
                valid &= data[address+0x800:address+0x809]==bytes([0x80 if 2<=row<7 else 0])*9
            if valid: break
            if time.monotonic()>deadline: raise AssertionError(('running panel',tag,rows))
            time.sleep(.1)
        records.append(dict(panel=tag,rows=rows)); print('PASS panel',tag,flush=True)
    def app_address(slot,symbol):
        return (0x2300,0x3500)[slot]+app_symbols['_udeks_native_clock_'+symbol][0]-0x1000
    def wait_task(offset,value,deadline):
        while capture('task-state',slots+offset,1)[0]!=value:
            if time.monotonic()>deadline: raise TimeoutError(('task state',offset,value))
            time.sleep(.1)
    def command(line,contains='',foreground=False):
        deadline=time.monotonic()+150
        wait_task(1,4,deadline)
        before=byte(port,0xf3d8)
        type_command(port,queue,line,deadline)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline)
        if not foreground:
            wait_task(1,4,deadline); wait_task(2,2,deadline)
        while True:
            data=capture('console',segments['LOWBSS'][0],0x558)
            output='\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip()
                             for i in range(0,21*65,65))
            if contains in output: break
            if time.monotonic()>deadline: raise AssertionError((line,output))
            time.sleep(.1)
        records.append(dict(command=line,console=output)); print('PASS',line,flush=True)
    def check_clock(slot,tag,hour=None,minute=None,width=None,height=None):
        deadline=time.monotonic()+90
        while True:
            commands,metadata,retained,geometry=sp.capture_blocks(port,[
                (work/(tag+'-commands.bin'),app_address(slot,'commands'),app_address(slot,'commands')+343,'worker'),
                (work/(tag+'-time.bin'),app_address(slot,'hour'),app_address(slot,'hour')+2,'worker'),
                (work/(tag+'-retained.bin'),0xc600+slot*1280,0xc600+slot*1280+343,'worker'),
                (work/(tag+'-geometry.bin'),app_address(slot,'width'),app_address(slot,'width')+2,'worker')])
            h,m,presents=metadata
            w=int.from_bytes(geometry[:2],'little'); ht=geometry[2]
            if (h<24 and m<60 and presents and 48<=w<=320 and 48<=ht<=200 and
                    (hour is None or (h,m)==(hour,minute)) and
                    (width is None or (w,ht)==(width,height))):
                expected=clock_commands(h,m,w,ht)
                if commands==retained==expected: break
            if time.monotonic()>deadline:
                raise AssertionError((tag,metadata.hex(),geometry.hex(),'clock commands differ from independent oracle'))
            time.sleep(.1)
        expected=relocate_executable(program,(0x2300,0x3500)[slot],(0x1200,0xb00)[slot])[16:]
        if capture(tag+'-code',(0x2300,0x3500)[slot],len(expected),'worker')!=expected:
            raise AssertionError('loaded clock differs from relocated image')
        records.append(dict(check=tag,slot=slot+3,hour=h,minute=m,presents=presents,width=w,height=ht))
        return presents
    def pointer(x,y,buttons):
        if not pointer_original:
            for name,length,offsets in (('x',10,((3,0),(6,1))),('y',4,((1,2),)),('buttons',4,((1,3),))):
                address=exports['_udeks_pointer_'+name][0]
                original=capture('pointer-'+name,address,length)
                expected={'x':b'\x08\x78\xad\xd8\xf1\xae\xd9\xf1\x28\x60',
                    'y':b'\xad\xda\xf1\x60','buttons':b'\xad\xdb\xf1\x60'}[name]
                if original!=expected: raise ValueError('pointer getter changed')
                pointer_original.append((address,original)); patched=bytearray(original)
                for offset,relative in offsets:
                    patched[offset:offset+2]=(scratch+relative).to_bytes(2,'little')
                sp.write_kernel_blocks(port,[(scratch,bytes((12,0,40,0))),(address,patched)])
        sp.write_kernel_blocks(port,[(scratch,(x+12).to_bytes(2,'little')+bytes((y+40,buttons)))])
    def restore_pointer():
        if pointer_original:
            sp.write_kernel_blocks(port,pointer_original); pointer_original.clear()
    def resize(handle,x,y,width,height,new_width,new_height):
        pointer(x+width-3,y+height-3,0); sp.wait_for_byte(port,0xf24d,0,time.monotonic()+60)
        pointer(x+width-3,y+height-3,1); sp.wait_for_byte(port,0xf248,handle,time.monotonic()+60)
        pointer(x+new_width-1,y+new_height-1,1)
        sp.wait_for_byte(port,0xf24c,new_width&255,time.monotonic()+60)
        pointer(x+new_width-1,y+new_height-1,0)
        sp.wait_for_byte(port,0xf248,0,time.monotonic()+60)
        restore_pointer()
    def canvas(tag):
        deadline=time.monotonic()+90
        while True:
            start,end,_=segments['VICSHADOW']
            shadow,bitmap=sp.capture_blocks(port,[
                (work/(tag+'-shadow.bin'),start,end,'kernel'),
                (work/(tag+'-bitmap.bin'),0x6000,0x7f3f,'worker')])
            if shadow==bitmap: break
            if time.monotonic()>deadline: raise AssertionError('bitmap/shadow mismatch')
            time.sleep(.1)
        (work/(tag+'.png')).write_bytes(bitmap_preview(bitmap))
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        panel('boot',{1:'RUNNING',2:'NONE'})
        legacy=capture('legacy-before',0xf220,32)
        command('nclock &')
        sp.wait_for_byte(port,0xf246,1,time.monotonic()+90)
        first_handle=byte(port,0xf247)
        check_clock(0,'first-clock')
        command('date 03:15:00','03:15:00')
        check_clock(0,'first-set-time',3,15)
        command('clock2',foreground=True)
        sp.wait_for_byte(port,0xf246,2,time.monotonic()+90)
        sp.wait_for_byte(port,0xf184,8,time.monotonic()+90)
        check_clock(1,'second-clock')
        panel('two-clocks',{1:'RUNNING',2:'xinit',3:'nclock',4:'clock2'})
        handle=byte(port,0xf247)
        pointer(134,55,0); sp.wait_for_byte(port,0xf24d,0,time.monotonic()+60)
        pointer(134,55,1); sp.wait_for_byte(port,0xf248,handle,time.monotonic()+60)
        pointer(32,55,1); sp.wait_for_byte(port,0xf249,22,time.monotonic()+60)
        pointer(32,55,0); sp.wait_for_byte(port,0xf248,0,time.monotonic()+60)
        restore_pointer()
        check_clock(0,'first-after-drag'); check_clock(1,'second-after-drag')
        resize(handle,22,50,72,88,126,130)
        check_clock(1,'second-enlarged',width=126,height=130)
        check_clock(0,'first-unaffected',width=72,height=88)
        resize(handle,22,50,126,130,48,48)
        check_clock(1,'second-minimum',width=48,height=48)
        resize(handle,22,50,48,48,126,130)
        check_clock(1,'second-regrown',width=126,height=130)
        resize(first_handle,124,50,72,88,180,140)
        check_clock(0,'first-enlarged',width=180,height=140)
        check_clock(1,'second-unaffected',width=126,height=130)
        canvas('two-native-clocks')
        # Ctrl+C retires only foreground task 4; the independent peer survives.
        sp.write_kernel_blocks(port,[(queue,bytes((1,0xff,3,2))),(queue+64,bytes((1,0,1)))])
        sp.wait_for_byte(port,0xf246,1,time.monotonic()+90)
        sp.wait_for_byte(port,0xf184,0,time.monotonic()+90)
        wait_task(25,0,time.monotonic()+90)
        check_clock(0,'background-survives')
        panel('foreground-stopped',{2:'xinit',3:'nclock',4:''})
        command('clock2 &')
        sp.wait_for_byte(port,0xf246,2,time.monotonic()+90)
        check_clock(1,'reloaded-clock')
        command('date 21:45:00','21:45:00')
        check_clock(0,'first-changed-time',21,45); check_clock(1,'second-changed-time',21,45)
        if capture('legacy-after',0xf220,32)!=legacy:
            raise AssertionError('native clock touched legacy clock diagnostic state')
        # Preserve all four windows, including unchanged legacy compatibility.
        command('xclock &','xclock started &')
        sp.wait_for_byte(port,0xf246,3,time.monotonic()+90)
        command('xwave &','xwave started &')
        sp.wait_for_byte(port,0xf246,4,time.monotonic()+90)
        sp.wait_for_byte(port,0xf27a,21,time.monotonic()+150)
        command('cowsay native clocks','native clocks')
        check_clock(0,'four-apps-first'); check_clock(1,'four-apps-second')
        panel('four-apps',{1:'RUNNING',2:'xinit',3:'xclock',4:'xwave',5:'nclock',6:'clock2'})
        command('xinit -q','VIC-II graphics stopped')
        for offset in (17,25): wait_task(offset,0,time.monotonic()+90)
        command('echo reusable','reusable')
        panel('stopped',{1:'RUNNING',2:'NONE',3:'',4:'',5:'',6:''})
        if byte(port,0xf11b): raise AssertionError('task guard failure')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive,
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),
            fixture_sha256=hashlib.sha256(image).hexdigest(),
            program_sha256=hashlib.sha256(program).hexdigest(),
            slots=[3,4],relocated_code=True,commands_oracle=True,date_updates=True,
            drag=True,resize=True,targeted_ctrl_c=True,reload=True,legacy_state_untouched=True,
            four_app_compatibility=True,stack_guards=True,running_panel=True,records=records),indent=2)+'\n')
    finally:
        sp.terminate(proc,port); os.close(master)


if __name__=='__main__': main()

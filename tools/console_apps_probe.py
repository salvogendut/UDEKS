#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify independent console/foreground graphical apps through ordinary ush.

Uses injected keyboard events (including Ctrl+C), not direct loader calls.
Does not claim native mouse, background console input or hardware testing.
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
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--drive',choices=('1541','1571','1581'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    work=args.output.resolve(); work.mkdir(parents=True,exist_ok=True)
    console_program=(ROOT/'build/generic-apps/console/ARGS.BIN').read_bytes()
    graphical=(ROOT/'build/generic-apps/example/HELLO.BIN').read_bytes()
    disk_image=add_apps(args.disk.read_bytes(),[('ARGS.BIN',console_program),
        ('AGAIN.BIN',console_program),('HELLO.BIN',graphical),('SECOND.BIN',graphical)])
    disk=work/('test'+args.disk.suffix); disk.write_bytes(disk_image)
    text=(ROOT/'build/8502/udeks-8502.map').read_text()
    segments=map_segments(text); exports=map_exports(text)
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    port=choose_port()
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')
    records=[]
    def capture(name,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(name+'.bin'),address,address+size-1,bank)])[0]
    def screen():
        data=capture('console',segments['LOWBSS'][0],0x558)
        return '\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,21*65,65))
    def wait_task(offset,value,deadline):
        while capture('task-state',slots+offset,1)[0]!=value:
            if time.monotonic()>deadline: raise TimeoutError(('task state',offset,value))
            time.sleep(.1)
    def command(line,contains=(),exit_status=None,foreground=False):
        deadline=time.monotonic()+150
        wait_task(1,4,deadline)
        before=byte(port,0xf3d8)
        type_command(port,queue,line,deadline)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline)
        if not foreground:
            wait_task(1,4,deadline)
            wait_task(2,2,deadline)
        while True:
            output=screen()
            if all(value in output for value in contains): break
            if time.monotonic()>deadline: raise AssertionError((line,output))
            time.sleep(.1)
        if exit_status is not None and byte(port,0xf287)!=exit_status:
            raise AssertionError((line,'wrong exit',byte(port,0xf287),output))
        records.append(dict(command=line,console=output,exit=exit_status))
        print('PASS',line,flush=True)
    def interrupt(remaining):
        sp.write_kernel_blocks(port,[(queue,bytes((1,0xff,3,2))),(queue+64,bytes((1,0,1)))])
        sp.wait_for_byte(port,0xf246,remaining,time.monotonic()+90)
        sp.wait_for_byte(port,0xf184,0,time.monotonic()+90)
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        command('ls /bin',('args','again','hello','second'))
        command('df',('Available','Read-only mount'))
        # No graphics command: both launch paths must leave the VIC untouched.
        before=capture('vic-before',0xf1b0,24)
        command('args alpha beta',('[args]','[alpha]','[beta]','fresh BSS','stderr works'),37)
        command('again renamed',('[again]','[renamed]','fresh BSS'),37)
        if capture('vic-after',0xf1b0,24)!=before:
            raise AssertionError('console-only command changed VIC status')
        command('hello',foreground=True)
        sp.wait_for_byte(port,0xf246,1,time.monotonic()+90)
        sp.wait_for_byte(port,0xf184,4,time.monotonic()+90)
        interrupt(0)
        wait_task(17,0,time.monotonic()+60)
        command('echo foreground returned',('foreground returned',))
        command('hello &')
        sp.wait_for_byte(port,0xf246,1,time.monotonic()+90)
        command('second',foreground=True)
        sp.wait_for_byte(port,0xf246,2,time.monotonic()+90)
        sp.wait_for_byte(port,0xf184,8,time.monotonic()+90)
        interrupt(1)
        wait_task(25,0,time.monotonic()+60)
        peer=capture('peer-after-interrupt',slots+17,1)[0]
        if peer not in (2,3,4): raise AssertionError(('Ctrl+C killed background peer',peer))
        command('second &')
        sp.wait_for_byte(port,0xf246,2,time.monotonic()+90)
        command('xclock &')
        sp.wait_for_byte(port,0xf246,3,time.monotonic()+90)
        command('xwave &')
        sp.wait_for_byte(port,0xf246,4,time.monotonic()+90)
        sp.wait_for_byte(port,0xf27a,21,time.monotonic()+150)
        for line in ('args while graphics run','args reload'):
            command(line,('fresh BSS','stderr works'),37)
            if byte(port,0xf246)!=4: raise AssertionError('console damaged windows')
        command('cowsay console alive',('console alive',))
        command('xinit -q',('VIC-II graphics stopped',))
        sp.wait_for_byte(port,0xf246,0,time.monotonic()+90)
        for offset in (17,25): wait_task(offset,0,time.monotonic()+90)
        command('args final',('[final]','fresh BSS'),37)
        if byte(port,0xf11b): raise AssertionError('task stack guard failure')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive,
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),
            fixture_sha256=hashlib.sha256(disk_image).hexdigest(),
            console_sha256=hashlib.sha256(console_program).hexdigest(),
            graphical_sha256=hashlib.sha256(graphical).hexdigest(),
            arbitrary_names=True,arguments=True,stdout_stderr=True,exit_status=True,
            bss_reload=True,lazy_graphics=True,foreground_ctrl_c_both_slots=True,
            console_with_four_windows=True,records=records),indent=2)+'\n')
    finally:
        sp.terminate(proc,port); os.close(master)


if __name__=='__main__': main()

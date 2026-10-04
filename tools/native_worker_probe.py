#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Two ordinary native programs share bounded Z80 requests; no kernel app IDs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from add_disk_apps import add_apps
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from o65_to_udex import relocate_executable
from storage_shell_probe import sp,byte,keyboard_queue_address,type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port

ROOT=Path(__file__).resolve().parents[1]

def expected_surface():
    heights=(40,38,34,27,18,10,2,-4,-8,-9,-8,-5,-2,1,4,5,5,4,2,0,-2,-3,-4,-3,-2,0,1,2,3,3,2,1,-1,-2,-2)
    samples=[]
    for row in range(21):
        for col in range(25):
            high,low=sorted((abs(col-12)*5,abs(row-10)*6),reverse=True)
            index=min(34,((high+(low>>2)+(low>>3))*2+2)//5)
            samples.append(heights[index]&255)
    return bytes(samples)

def expected_wave(phase):
    # Frozen integer worker waveform, not a freshly rounded host libm sine.
    # Its +/-12 sample deliberately differs from round(30*sin(pi/8)).
    quarter=(0,3,6,9,12,14,17,19,21,23,25,26,28,29,29,30,30)
    result=[]
    for n in range(64):
        index=((phase+7*n)&255)>>2; half=index&31
        sample=quarter[half if half<=16 else 32-half]
        result.append((-sample if index>=32 else sample)&255)
    return bytes(result)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--drive',choices=('1541','1571','1581'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); work=args.output.resolve(); work.mkdir(parents=True,exist_ok=True)
    program=(ROOT/'build/native-clients/worker/WORKER.BIN').read_bytes()
    image=add_apps(args.disk.read_bytes(),[('WORKER.BIN',program),('PEER.BIN',program)])
    disk=work/('native-worker'+args.disk.suffix); disk.write_bytes(image)
    text=(ROOT/'build/8502/udeks-8502.map').read_text(); segments=map_segments(text)
    symbols=map_exports((ROOT/'build/native-clients/worker/worker_probe.map').read_text())
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    port=choose_port(); proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')
    records=[]
    def address(slot,field): return (0x2300,0x3500)[slot]+symbols['_worker_'+field][0]-0x1000
    def capture(name,where,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(name+'.bin'),where,where+size-1,bank)])[0]
    def wait_app(slot,value):
        deadline=time.monotonic()+90
        while True:
            state=capture('state-'+str(slot),address(slot,'state'),1,'worker')[0]
            if state==value: return
            if state==0x80 or time.monotonic()>deadline:
                raise AssertionError(('worker state',slot,state,capture('failure',address(slot,'failure'),1,'worker')))
            time.sleep(.1)
    def command(line,contains=''):
        deadline=time.monotonic()+150
        before=byte(port,0xf3d8)
        type_command(port,queue,line,deadline)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline)
        while True:
            state=capture('shell-state',slots+1,1)[0]
            data=capture('console',segments['LOWBSS'][0],0x558)
            output='\n'.join(data[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
            if state==4 and contains in output: break
            if time.monotonic()>deadline: raise AssertionError((line,state,output))
            time.sleep(.1)
        records.append(dict(command=line,console=output)); print('PASS',line,flush=True)
    def verify(slot,tag):
        samples=capture(tag+'-samples',address(slot,'samples'),525,'worker')
        wave=capture(tag+'-wave',address(slot,'wave'),64,'worker')
        phase=capture(tag+'-phase',address(slot,'phase'),1,'worker')[0]
        steps=capture(tag+'-steps',address(slot,'steps'),1,'worker')[0]
        if samples!=expected_surface() or wave!=expected_wave(phase) or steps!=21:
            raise AssertionError(('math/private copy',tag,steps,phase))
        code=relocate_executable(program,(0x2300,0x3500)[slot],(0x1200,0xb00)[slot])[16:]
        if capture(tag+'-code',(0x2300,0x3500)[slot],len(code),'worker')!=code:
            raise AssertionError('native program overwritten')
        records.append(dict(check=tag,slot=slot+3,steps=steps,phase=phase))
        print('PASS',tag,flush=True)
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        command('worker &'); wait_app(0,1)
        command('peer &'); wait_app(1,1)
        if byte(port,0xf1b5)==3: raise AssertionError('console workers initialized graphics')
        before=capture('engine-before',0xf190,32)
        sp.write_blocks(port,[(address(0,'command'),b'\x01'),(address(1,'command'),b'\x01')],'worker')
        command('echo worker clients alive','worker clients alive')
        for slot in range(2): wait_app(slot,3); verify(slot,'client-'+str(slot))
        after=capture('engine-after',0xf190,32)
        # Per client: one rejected row lease + NOP + 21 rows + 64-sample wave.
        if ((int.from_bytes(after[12:14],'little')-int.from_bytes(before[12:14],'little'))&65535)!=46:
            raise AssertionError('unexpected successful worker lease count')
        if ((int.from_bytes(after[14:16],'little')-int.from_bytes(before[14:16],'little'))&65535)!=2:
            raise AssertionError('unexpected rejected worker lease count')
        command('xclock &','xclock started &')
        command('xwave &','xwave started &')
        sp.wait_for_byte(port,0xf27a,21,time.monotonic()+150)
        command('cowsay worker API','worker API')
        for slot in range(2): verify(slot,'after-legacy-'+str(slot))
        sp.write_blocks(port,[(address(0,'command'),b'\x02'),(address(1,'command'),b'\x02')],'worker')
        for offset in (17,25):
            deadline=time.monotonic()+90
            while capture('reaped-'+str(offset),slots+offset,1)[0]:
                if time.monotonic()>deadline: raise AssertionError('worker was not reaped')
                time.sleep(.1)
        command('worker &'); wait_app(0,1)
        if any(capture('fresh-bss',address(0,'samples'),525,'worker')): raise AssertionError('stale BSS on reload')
        sp.write_blocks(port,[(address(0,'command'),b'\x02')],'worker')
        deadline=time.monotonic()+90
        while capture('reload-reaped',slots+17,1)[0]:
            if time.monotonic()>deadline: raise AssertionError('reloaded worker did not exit/reap')
            time.sleep(.1)
        command('xinit -q','VIC-II graphics stopped')
        command('echo worker cleanup passed','worker cleanup passed')
        if byte(port,0xf11b): raise AssertionError('task guard failure')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive,
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),
            fixture_sha256=hashlib.sha256(image).hexdigest(),program_sha256=hashlib.sha256(program).hexdigest(),
            slots=[3,4],surface_oracle=True,wave_oracle=True,private_results=True,sequence_checked=True,
            errors_return=True,lease_counts=True,console_live=True,lazy_graphics=True,
            legacy_coexistence=True,reap_reload=True,stack_guards=True,records=records),indent=2)+'\n')
    finally:
        sp.terminate(proc,port); os.close(master)

if __name__=='__main__': main()

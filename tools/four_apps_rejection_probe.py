#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""VICE malformed/fifth-image rejection with three/four live graphical peers.

Invoke the private loader at a restored root poll boundary. Scratch is measured
unused graphics-output padding plus the resident/LOWBSS gap; never live code.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from banked_loader_probe import request_record
from boot_staging_map import segment_bounds
from build_d71 import install_prg_file
from build_udex import build_executable
from gen_capability_imports import map_exports
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port

ROOT=Path(__file__).resolve().parents[1]


def hook(code, data, poll, selector):
    def word(n):return n.to_bytes(2,'little')
    # Save all 38 request bytes on the kernel hardware stack. Replace them
    # only at the safe poll entry, restore them before the original C prologue.
    result=bytearray(b'\xa2\x25')
    result+=b'\xbd\x59\xf3\x48\xbd'+word(data)+b'\x9d\x59\xf3\xca\x10\xf3'
    result+=bytes((0xa9,selector))+b'\x20\x1c\xf9\x8d'+word(data+38)
    result+=b'\xa2\0\x68\x9d\x59\xf3\xe8\xe0\x26\xd0\xf7'
    result+=b'\xa2\x02\xbd'+word(data+39)+b'\x9d'+word(poll)+b'\xca\x10\xf7'
    result+=b'\xee'+word(data+42)+b'\x4c'+word(poll)
    return bytes(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive',choices=('1541','1571'),default='1541')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    work=args.output.resolve();work.mkdir(parents=True,exist_ok=True)
    text=(ROOT/'build/8502/udeks-8502.map').read_text()
    exports=map_exports(text)
    code=segment_bounds(text,'GRAPHICSCODE')[1]+1
    data=segment_bounds(text,'BSS')[1]+1
    poll=exports['_udeks_shell_poll'][0]
    if code+len(hook(code,data,poll,4))>0x1200 or data+43>segment_bounds(text,'LOWBSS')[0]:
        raise ValueError('no map-proven scratch for rejection hook')
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    console_base=segment_bounds(text,'LOWBSS')[0]
    original_disk=args.disk.read_bytes();image=bytearray(original_disk)
    valid=build_executable(b'\xa9\x25\x60',cpu=1,load_address=0x3500,entry_address=0x3500)
    files={'xextra':valid}
    for name,offset,value in (('badmagic',0,0),('badslot',9,0x23),('badbss',13,0xff)):
        candidate=bytearray(valid);candidate[offset]=value;files[name]=candidate
    for name,program in files.items():install_prg_file(image,name.upper()+'.BIN',program,file_type=0x81)
    disk=work/('test'+args.disk.suffix);disk.write_bytes(image)
    port=choose_port()
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')
    records=[]
    def capture(name,address,size,bank='kernel'):
        return sp.capture_blocks(port,[(work/(name+'.bin'),address,address+size-1,bank)])[0]
    def command(line,expected):
        deadline=time.monotonic()+150;sp.wait_for_byte(port,slots+1,4,deadline)
        before=byte(port,0xf3d8);type_command(port,queue,line,deadline)
        sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline)
        while time.monotonic()<deadline:
            cells=capture('console',console_base,0x558)
            output='\n'.join(cells[n:n+64].decode('ascii',errors='replace') for n in range(0,21*65,65))
            if expected in output:break
            time.sleep(.1)
        else:raise AssertionError((line,output))
        records.append(dict(command=line,console=output))
    def invoke(name,error,selector=4):
        sp.wait_for_byte(port,slots+1,4,time.monotonic()+60)
        original=capture('poll',poll,3)
        stub=hook(code,data,poll,selector)
        padding=capture('padding',code,len(stub))
        sp.write_kernel_blocks(port,[(data,request_record(name)+b'\0'+original+b'\0'),
            (code,stub),(poll,b'\x4c'+code.to_bytes(2,'little'))])
        sp.wait_for_byte(port,data+42,1,time.monotonic()+150)
        reply=capture('reply',data,43)
        if reply[38]!=error or capture('restored-poll',poll,3)!=original:
            raise AssertionError((name,error,reply.hex()))
        # The original entry is already restored before DONE. It is now safe
        # to retire hook padding after a further shell service turn.
        command('echo rejected '+name,'rejected '+name)
        sp.write_kernel_blocks(port,[(code,padding)])
        records.append(dict(candidate=name,selector=selector,errno=error))
        print('PASS',name,error,flush=True)
    def protected(tag,draw=False):
        blocks=[]
        for name,address,bank in (('xclock',0x200,'kernel'),('xwave',0x1200,'kernel'),
                                  ('xcalc',0x2300,'worker'),('xdraw',0x3500,'worker')):
            if name=='xdraw' and not draw:continue
            blocks.append(capture(tag+'-'+name,address,len((ROOT/('build/user/'+name+'.udx')).read_bytes())-16,bank))
        blocks.append(capture(tag+'-retained',0xc600,2560 if draw else 1280,'worker'))
        return blocks
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        for name in ('xclock','xwave','xcalc'):
            command(name+' &',name+' started &')
            if name=='xwave':sp.wait_for_byte(port,0xf27a,21,time.monotonic()+90)
        sp.wait_for_byte(port,0xf246,3,time.monotonic()+90)
        before=protected('before-invalid')
        for name,error in (('absent',2),('badmagic',8),('badslot',8),('badbss',12)):
            invoke(name,error)
            if protected('after-'+name)!=before or byte(port,0xf246)!=3:
                raise AssertionError('failed fourth load damaged a peer: '+name)
        command('xdraw &','xdraw started &')
        sp.wait_for_byte(port,0xf246,4,time.monotonic()+90)
        before=protected('before-fifth',True)
        invoke('xextra',16)
        if protected('after-fifth',True)!=before or byte(port,0xf246)!=4:
            raise AssertionError('fifth image damaged a live application')
        command('cowsay rejection survived','rejection survived')
        command('xdraw -q','xdraw stopped')
        sp.wait_for_byte(port,0xf246,3,time.monotonic()+90)
        command('xdraw &','xdraw started &')
        sp.wait_for_byte(port,0xf246,4,time.monotonic()+90)
        if byte(port,0xf11b):raise AssertionError('lifecycle canary failure')
        (work/'result.json').write_text(json.dumps(dict(
            disk_sha256=hashlib.sha256(original_disk).hexdigest(),
            fixture_sha256=hashlib.sha256(image).hexdigest(),drive=args.drive,
            scratch=dict(code=code,data=data,hook_size=len(hook(code,data,poll,4))),
            peers_unchanged=True,fourth_reload=True,records=records),indent=2)+'\n')
    finally:
        sp.terminate(proc,port);os.close(master)


if __name__=='__main__':main()

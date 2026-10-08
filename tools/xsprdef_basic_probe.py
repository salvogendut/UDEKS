#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Load an editor export through stock C128 BASIC, then BSAVE it back.

Uses a disposable disk copy; only BASIC writes the target RAM and roundtrip
file. No monitor LOAD, synthetic KERNAL call or machine-code loader is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import time

import shadow_boot_probe as sp
import build_d81 as d81
from build_d71 import blank_d71, d64_compatibility_image, sector_offset
from build_d81 import blank_d81
from storage_public_probe import files
from vice_capture import choose_port, monitor_command, receive_prompts, quote_monitor_path


def basic_bank(raw):
    if len(raw)!=504:raise ValueError('sprite bank must be 504 bytes')
    return b'\x00\x0e'+b''.join(raw[n:n+63]+b'\0' for n in range(0,504,63))


def qualify(source,drive,work):
    work=Path(work).resolve();work.mkdir(parents=True,exist_ok=True)
    original=Path(source).read_bytes();before=files(original)
    exported=before[b'SPRITES.BSV']
    offset,start=(d81.sector_offset,(40,3)) if len(original)==d81.SIZE else (sector_offset,(18,1))
    entry=next(e for e in d81.entries(original,offset,*start) if e[3:19].rstrip(b'\xa0')==b'SPRITES.BSV')
    if entry[0]!=0x82:raise AssertionError('BASIC export must be a closed PRG')
    if len(exported)!=514 or exported[:2]!=b'\0\x0e' or any(exported[65::64]):
        raise AssertionError('invalid BASIC export')
    if b'ROUNDTRIP' in before:raise ValueError('qualification needs a fresh ROUNDTRIP filename')
    disk=work/('roundtrip'+Path(source).suffix);disk.write_bytes(original)
    blank=work/('blank'+Path(source).suffix)
    blank.write_bytes(blank_d81() if drive=='1581' else
        d64_compatibility_image(blank_d71()) if drive=='1541' else blank_d71())
    port=choose_port()
    proc,master=sp.launch_vice(blank,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',drive),log_path=work/'vice.log')

    def command(line,marker):
        # VICE keybuf is host text: lowercase letters type unshifted PETSCII
        # $41-$5A in the stock upper/graphics charset. Host capitals type the
        # shifted $C1-$DA range and would request a different DOS filename.
        print('BASIC:',line,flush=True)
        monitor_command(port,'keybuf '+line.lower()+'\\n')
        sp.wait_for_byte(port,2816,marker,time.monotonic()+150)

    def capture(tag,start,end):
        path=work/(tag+'.bin')
        with socket.create_connection(('127.0.0.1',port),timeout=3) as connection:
            connection.settimeout(15)
            try:
                connection.sendall(b'bank ram00\n');receive_prompts(connection,2)
                connection.sendall(b'bank\n');reply=receive_prompts(connection)
                if b'*ram00-01(00)' not in reply:raise RuntimeError(reply)
                connection.sendall(f'save {quote_monitor_path(path)} 0 {start:04x} {end:04x}\n'.encode())
                if b'Saving' not in receive_prompts(connection):raise RuntimeError('capture refused')
            finally:
                connection.sendall(b'bank cpu\n');receive_prompts(connection)
                connection.sendall(b'x\n')
        return path.read_bytes()[2:]

    try:
        # Empty, non-bootable media enters ordinary BASIC instead of UDEKS.
        time.sleep(5)
        command('bank0:poke2816,165',165)
        monitor_command(port,f'attach {quote_monitor_path(disk)} 8')
        command('dclear:poke2816,171',171)
        for index,placement in enumerate((',p3584','')):
            marker=166+index*2
            command('bank0:fori=3583to4096:pokei,90:next:poke2816,'+str(marker),marker)
            line='bload"SPRITES.BSV",b0'+placement
            command(line+':poke2816,'+str(marker+1),marker+1)
            actual=capture('loaded-'+str(index),3583,4096)
            if actual!=b'Z'+exported[2:]+b'Z':
                raise AssertionError(('BLOAD bytes/guards disagree',line,actual.hex()))
            print('PASS stock BASIC:',line,flush=True)
        command('bsave"ROUNDTRIP",b0,p3584top4096:poke2816,170',170)
    except Exception:
        (work/'registers.txt').write_bytes(monitor_command(port,'r'))
        capture('basic-screen',0x400,0x7e7)
        raise
    finally:
        sp.terminate(proc,port)
        if master is not None:os.close(master)
    after=files(disk.read_bytes())
    if any(after.get(n)!=v for n,v in before.items()):raise AssertionError('existing file changed')
    if {n:v for n,v in after.items() if n not in before}!={b'ROUNDTRIP':exported}:
        raise AssertionError('BASIC BSAVE differs from editor export')
    if Path(source).read_bytes()!=original:raise AssertionError('source image changed')
    result=dict(drive=drive,source_sha256=hashlib.sha256(original).hexdigest(),
        export_sha256=hashlib.sha256(exported).hexdigest(),bload_explicit_and_header=True,
        guard_bytes_unchanged=True,bsave_byte_identical=True)
    (work/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS stock BASIC BLOAD/BSAVE compatibility:',work,flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--drive',choices=('1541','1571','1581'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    qualify(args.disk,args.drive,args.output)

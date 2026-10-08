#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify real RC/disk service loading on a disposable VICE boot image.

Uses matching candidate maps and the ordinary shell keyboard queue. No monitor
call installs the service, executes its API, or fabricates a TIME snapshot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

import build_d71 as d71
import build_d81 as d81
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from service_image import TIME_BASE, seal
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port

ROOT = Path(__file__).resolve().parents[1]


def damage_module(image, suffix, mode):
    result = bytearray(image)
    offset, track, sector = (d81.sector_offset, 40, 3) if suffix == '.d81' else (d71.sector_offset, 18, 1)
    seen = set()
    while track:
        pos = offset(track, sector)
        if pos in seen:
            raise ValueError('cyclic directory')
        seen.add(pos)
        for slot in range(8):
            entry = pos+2+slot*32
            if result[entry] and result[entry+3:entry+19].rstrip(b'\xa0') == b'TIME.SVC':
                if mode == 'missing':
                    result[entry+3:entry+19] = b'KEEP.SVC'.ljust(16, b'\xa0')
                else:
                    start = offset(result[entry+1], result[entry+2])+2
                    result[start+16] ^= 1  # checksum only; format remains valid
                return bytes(result)
        track, sector = result[pos:pos+2]
    raise ValueError('TIME.SVC not found')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, default=ROOT/'build/services/boot/latest.json')
    parser.add_argument('--format', choices=('d64','d71','d81'), default='d64')
    parser.add_argument('--mode', choices=('healthy','missing','corrupt'), default='healthy')
    parser.add_argument('--output', type=Path, default=ROOT/'build/services/boot/vice')
    args = parser.parse_args()
    candidate = json.loads(args.candidate.read_text())
    source = Path(candidate['source'])
    original_path = Path(candidate['disks'][args.format]['path'])
    original = original_path.read_bytes()
    if hashlib.sha256(original).hexdigest() != candidate['disks'][args.format]['sha256']:
        raise ValueError('candidate disk hash changed')
    args.output.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=args.format+'-'+args.mode+'-', dir=args.output.resolve()))
    disk = work/('disposable.'+args.format)
    module = (source/'build/services/time/TIME.SVC').read_bytes()
    replacement = bytearray(module)
    replacement[18:20] = b'\2\0'
    replacement = seal(replacement)
    image = original if args.mode == 'healthy' else damage_module(original, disk.suffix, args.mode)
    # An independent revision is a disk-only replacement, not a kernel link.
    if args.format == 'd81':
        image = bytearray(image)
        d81.install_file(image,'TIME2.SVC',replacement)
    else:
        image = d71.add_data_files(image,[('TIME2.SVC',replacement)],70 if args.format=='d71' else 35)
    disk.write_bytes(image)
    map_text = (source/'build/8502/udeks-8502.map').read_text()
    layout, exports = map_segments(map_text), map_exports(map_text)
    queue = keyboard_queue_address(map_text, (source/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(source/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    state = exports['_udeks_time_slot_state'][0]
    drive = dict(d64='1541', d71='1571', d81='1581')[args.format]
    port = choose_port()
    records = []
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
        ('-console', '-jamaction', '5', '-drive8truedrive', '-drive8type', drive),
        log_path=work/'vice.log')

    def capture(tag, address, size):
        path = work/(tag+'.bin')
        raw = sp.capture_blocks(port, [(path,address,address+size-1,'kernel')])[0]
        path.write_bytes(raw)
        return raw

    def prompt():
        deadline = time.monotonic()+120
        while time.monotonic() < deadline:
            if capture('prompt', slots+1, 2) == b'\4\2':
                return
            time.sleep(.05)
        raise TimeoutError('shell prompt')

    def command(line, contains='', status=0):
        prompt()
        previous = byte(port, 0xf3d8)
        type_command(port, queue, line, time.monotonic()+120)
        sp.wait_for_byte(port, 0xf3d8, (previous+1)&255, time.monotonic()+120)
        prompt()
        cells = capture('console', layout['LOWBSS'][0], 0x558)
        output = '\n'.join(cells[i:i+64].decode('ascii',errors='replace').rstrip()
                           for i in range(0,1365,65))
        actual = byte(port,0xf287)
        if contains not in output or actual != status:
            raise AssertionError((line, actual, status, output))
        records.append(dict(command=line, exit=actual, console=output))
        print('PASS',line,flush=True)

    def published(expected):
        actual = capture('service-state',state,1)[0]
        if actual != expected or (byte(port,0xf205)==2) != (expected==2):
            raise AssertionError(('publication',actual,expected))

    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        prompt()
        if args.mode == 'healthy':
            command('svc status','time: ready')
            published(2)
            if capture('installed-image',TIME_BASE,len(module)) != module:
                raise AssertionError('installed module differs from disk file')
            command('date -s 12:34:00')
            command('date','12:34:')
            command('xclock &')
            sp.wait_for_byte(port,0xf246,1,time.monotonic()+120)
            command('svc stop','time: offline')
            published(0)
            sp.wait_for_byte(port,0xf246,0,time.monotonic()+120)
            command('date','date: time service unavailable',1)
            command('svc load /NOFILE','No such file or directory',1)
            published(0)
            command('svc load','time: ready')
            published(2)
            command('svc load','busy',1)
            published(2)
            command('date','12:34:')
            command('xclock &')
            sp.wait_for_byte(port,0xf246,1,time.monotonic()+120)
            command('xclock -q')
            sp.wait_for_byte(port,0xf246,0,time.monotonic()+120)
            command('svc stop','time: offline')
        else:
            command('svc status','time: offline')
            published(0)
            command('date','date: time service unavailable',1)
            command('svc load', 'No such file or directory' if args.mode=='missing' else 'Exec format error',1)
            published(0)
        command('svc load /TIME2.SVC','time: ready')
        published(2)
        if capture('replacement-image',TIME_BASE,len(replacement)) != replacement:
            raise AssertionError('disk-only replacement was not installed exactly')
        command('date')
        command('cat /hello','HELLO UDEKS')
        if byte(port,0xf11b):
            raise AssertionError('task canary failure')
        result = dict(scope='real disk/RC service integration, ordinary keyboard commands',
            source=str(source), drive=drive, mode=args.mode,
            source_disk_sha256=hashlib.sha256(original).hexdigest(),
            test_disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),commands=records)
        (work/'report.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS disk service; evidence:',work,flush=True)
    finally:
        sp.terminate(proc,port)
        os.close(master)
    if original_path.read_bytes()!=original:
        raise AssertionError('source disk changed')


if __name__ == '__main__':
    main()

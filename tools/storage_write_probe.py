#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the PRIVATE writer on freshly generated disposable VICE disks.

This does not enable a UDEKS syscall. No input disk option is provided: each run
gets a new temporary directory below build/, a blank image and a sentinel file.
The program writes ten create-only SEQ files, checks duplicate rejection, reads
exact bytes through UDEKS's sector reader, then repeats the read in a fresh VICE
process. The host independently checks the resulting directory/file chains.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_d71 import blank_d71, d64_compatibility_image, install_prg_file, sector_offset
import build_d81 as d81

ROOT = Path(__file__).resolve().parents[1]
LENGTHS = (1, 2, 23, 24, 253, 254, 255, 256, 508, 515)
KEEP = bytes(range(255, -1, -1))*3


def samples():
    return {f'WRTEST0{i}': bytes(n % 256 for n in range(size)) for i, size in enumerate(LENGTHS)}


def make_disk(drive):
    if drive == '1581':
        image = d81.blank_d81(name=b'WRITE PROBE')
        d81.install_file(image, 'KEEP', KEEP)
        return bytes(image)
    image = blank_d71()
    install_prg_file(image, 'KEEP', KEEP, file_type=0x81)
    return bytes(d64_compatibility_image(image) if drive == '1541' else image)


def read_files(image, drive):
    offset = d81.sector_offset if drive == '1581' else sector_offset
    directory = (40, 3) if drive == '1581' else (18, 1)
    files = {}
    for entry in d81.entries(image, offset, *directory):
        name = entry[3:19].rstrip(b'\xa0').decode('ascii')
        if name in files or entry[0] != 0x81:
            raise AssertionError(f'duplicate, splat or unexpected type: {name} {entry.hex()}')
        files[name] = d81.file_bytes(image, entry, offset)
    return files


def run(drive):
    base = ROOT/'build/storage/write-probe'
    base.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=drive+'-', dir=base))
    program = work/'write.prg'
    shutil.copyfile(ROOT/'build/bench/iec-write/write.prg', program)
    extension = {'1541': '.d64', '1571': '.d71', '1581': '.d81'}[drive]
    disk = work/('disposable'+extension)
    original = make_disk(drive)
    disk.write_bytes(original)
    (work/('before'+extension)).write_bytes(original)
    records = []
    for mode, phase in ((3, 'write-protected'), (0, 'create-read'),
                        (1, 'reboot-read'), (2, 'empty-diagnostic')):
        raw = work/(phase+'.bin')
        command = ['python3', 'tools/vice_capture.py', str(program), str(raw),
                   '--raw-load', '--entry', '0x2800', '--result-address', '0x6000',
                   '--result-size', '0x20', '--state-offset', '0', '--complete-value', '2',
                   '--timeout', '120', '--poll-delay', '4', '--capture-incomplete',
                   '--poke', f'0x60f0={mode}', '--vice-arg=-drive8truedrive',
                   '--vice-arg=-drive8type', '--vice-arg='+drive,
                   '--vice-arg=-8', '--vice-arg='+str(disk)]
        if mode == 3: command.append('--vice-arg=-attach8ro')
        with (work/(phase+'.log')).open('w') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            detail = raw.read_bytes().hex() if raw.exists() else 'no record'
            raise RuntimeError(f'{drive} {phase}: {detail}; see {work}')
        record = raw.read_bytes()
        if len(record) != 32 or record[0] != 2:
            raise AssertionError(f'bad probe record: {record.hex()}')
        actual = read_files(disk.read_bytes(), drive)
        if mode == 3:
            if record[2:4] != bytes((10, 30)) or record[8:10] != record[10:12] or disk.read_bytes() != original:
                raise AssertionError('write protection did not preserve the disk/context or return EROFS')
            print(f'{drive} write protection: EROFS, image unchanged', flush=True)
        elif mode == 2:
            if record[2] != 9 or 'EMPTY' not in actual:
                raise AssertionError('empty-file diagnostic did not complete')
            empty = actual.pop('EMPTY')
            print(f'{drive} empty-file diagnostic: {len(empty)} byte(s), {empty.hex()}; NOT an exact-empty qualification', flush=True)
        elif record[12] != 10 or record[8:10] != record[10:12]:
            raise AssertionError(f'bad readback/speed/bank record: {record.hex()}')
        if mode != 3 and actual != samples() | {'KEEP': KEEP}:
            raise AssertionError(f'{drive}: independent on-disk readback differs')
        records.append({'phase': phase, 'record': record.hex(),
                        'disk_sha256': hashlib.sha256(disk.read_bytes()).hexdigest()})
        if mode in (0, 1):
            print(f'{drive} {phase}: 10 exact files, KEEP intact, CPU speed/VIC bank preserved', flush=True)
    if records[1]['disk_sha256'] != records[2]['disk_sha256']:
        raise AssertionError('read-only reboot changed the disk')
    result = {'drive': drive, 'lengths': LENGTHS, 'records': records,
              'empty_file': {'intended_size': 0, 'actual': empty.hex(), 'qualified': False},
              'program_sha256': hashlib.sha256(program.read_bytes()).hexdigest(),
              'before_sha256': hashlib.sha256(original).hexdigest()}
    (work/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(f'evidence: {work}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--drive', choices=('1541', '1571', '1581', 'all'), default='all')
    args = parser.parse_args()
    for drive in (('1541', '1571', '1581') if args.drive == 'all' else (args.drive,)):
        run(drive)


if __name__ == '__main__': main()

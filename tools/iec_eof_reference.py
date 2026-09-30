#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare tiny on-disk files with stock C128 KERNAL/DOS, not UDEKS."""
import argparse
import json
from pathlib import Path
import subprocess
from build_d71 import blank_d71, d64_compatibility_image, install_prg_file

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--drive', choices=('1541', '1571'), default='1541')
    args = p.parse_args()
    work = ROOT/'build/storage/eof-reference'/args.drive
    work.mkdir(parents=True, exist_ok=True)
    records = []
    for name, data in (('empty', b''), ('nul', b'\0'), ('one', b'X'), ('two', b'XY')):
        image = blank_d71()
        install_prg_file(image, 'ONE', data, file_type=0x81)
        disk = work/(name+'.d64')
        disk.write_bytes(d64_compatibility_image(image))
        raw = work/(name+'.bin')
        subprocess.run(['python3', 'tools/vice_capture.py',
            'build/bench/iec-directory/kernal-eof.prg', str(raw),
            '--raw-load', '--entry', '0x2800', '--result-address', '0x3100',
            '--result-size', '0x200', '--state-offset', '0', '--complete-value', '2',
            '--timeout', '60', '--poll-delay', '2', '--capture-incomplete',
            '--vice-arg=-drive8truedrive', '--vice-arg=-drive8type',
            '--vice-arg='+args.drive, '--vice-arg=-8', '--vice-arg='+str(disk)], cwd=ROOT, check=True)
        result = raw.read_bytes()
        if len(result) != 512 or result[0] != 2 or result[2] != 64:
            raise AssertionError('stock KERNAL run did not finish with EOI')
        size = int.from_bytes(result[4:6], 'little')
        actual = result[256:256+size]
        records.append({'name': name, 'expected': data.hex(), 'actual': actual.hex(),
                        'state': result[0], 'status': result[2], 'size': size})
        print(f'{name}: {size} bytes; ST={result[2]:02x}; exact={actual == data}', flush=True)
    (work/'result.json').write_text(json.dumps(records, indent=2)+'\n')


if __name__ == '__main__': main()

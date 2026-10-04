#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add independently built NAME.BIN files to a NEW UDEKS disk-image copy.

The kernel is not rebuilt. Inputs and existing outputs are never overwritten.
Executables are stored as raw-byte closed SEQ files, not PRG load streams.
"""
import argparse
from pathlib import Path
import re
from build_d71 import D64_SIZE, blank_d71, install_prg_file, sector_offset
import build_d81


def directory_names(image):
    if len(image) == build_d81.SIZE:
        return {e[3:19].rstrip(b'\xa0').upper()
                for e in build_d81.entries(image, build_d81.sector_offset, 40, 3)}
    if len(image) not in (D64_SIZE, len(blank_d71())):
        raise ValueError('expected a standard D64, D71 or D81')
    sector, seen, names = 1, set(), set()
    while True:
        pos = sector_offset(18, sector)
        if sector in seen:
            raise ValueError('cyclic directory')
        seen.add(sector)
        for slot in range(8):
            entry = pos + 2 + 32 * slot
            if image[entry]:
                names.add(bytes(image[entry+3:entry+19]).rstrip(b'\xa0').upper())
        track, sector = image[pos:pos+2]
        if not track:
            return names
        if track != 18 or not sector:
            raise ValueError('invalid directory link')


def add_apps(image, files):
    """Validate names before allocating on a private copy; reject collisions."""
    names = directory_names(image)
    pending = []
    for name, data in files:
        name = name.upper()
        if not re.fullmatch(r'[A-Z0-9_-]{1,12}\.BIN', name):
            raise ValueError('expected a portable DOS filename: 1..12 letters/digits/_/- + .BIN')
        key = name.encode('ascii')
        if key in names:
            raise ValueError('disk filename already exists: ' + name)
        if len(data) < 17 or data[:4] != b'UDEX':
            raise ValueError('not a UDEX executable: ' + name)
        names.add(key)
        pending.append((name, data))
    result = bytearray(image)
    install = build_d81.install_file if len(image) == build_d81.SIZE else install_prg_file
    for name, data in pending:
        install(result, name, data, file_type=0x81)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('apps', nargs='+', type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error('output already exists; choose a new image name')
    try:
        result = add_apps(args.disk.read_bytes(), [(p.name, p.read_bytes()) for p in args.apps])
        with args.output.open('xb') as out:
            out.write(result)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print('Created', args.output, 'with', len(args.apps), 'additional executable(s)')


if __name__ == '__main__':
    main()

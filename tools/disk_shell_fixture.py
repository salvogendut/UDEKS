#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Change only the DOS USH file, never the boot payload or bootfs recovery copy."""
import argparse
from pathlib import Path
from build_d71 import sector_offset


def shell_file(image):
    """Return directory entry and ordered payload byte offsets; reject bad chains."""
    directory = sector_offset(18, 1)
    entries = [directory+2+32*i for i in range(8)]
    matches = [p for p in entries if image[p] == 0x81 and
               image[p+3:p+19].rstrip(b'\xa0') == b'USH']
    if len(matches) != 1:
        raise ValueError('expected exactly one closed SEQ USH in the first directory sector')
    entry = matches[0]
    track, sector = image[entry+1:entry+3]
    offsets, seen = [], set()
    while track:
        pos = sector_offset(track, sector)
        if pos in seen or pos+256 > len(image):
            raise ValueError('invalid USH chain')
        seen.add(pos)
        track, sector = image[pos:pos+2]
        count = 254 if track else sector-1
        if not 0 <= count <= 254:
            raise ValueError('invalid USH terminal byte count')
        offsets.extend(range(pos+2, pos+2+count))
    return entry, offsets


def build_fixture(image, variant):
    entry, offsets = shell_file(image)
    payload = bytes(image[p] for p in offsets)
    result = bytearray(image)
    if variant == 'missing':
        # Hide the entry in this disposable fixture; keep the BAM/boot bytes.
        result[entry] = 0
        return bytes(result)
    if len(payload) < 17 or payload[:10] != b'UDEX\0\x01\x01\x01\0\x90':
        raise ValueError('expected persistent 8502 UDEX at $9000')
    if variant == 'bad':
        result[offsets[0]] = 0
    elif variant == 'entry':
        result[offsets[14]] = 1
    elif variant == 'flags':
        result[offsets[7]] = 0
    elif variant in ('diskA', 'diskB'):
        marker = b'UDEKS 0.1.0 c128 8502'
        if payload.count(marker) != 1:
            raise ValueError('shell version marker must occur exactly once')
        changed = payload.replace(marker, b'UDEKS '+variant.encode()+b' c128 8502')
        for p, value in zip(offsets, changed, strict=True):
            result[p] = value
    else:
        raise ValueError('unknown shell fixture variant')
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disk', type=Path)
    parser.add_argument('variant', choices=('diskA', 'diskB', 'missing', 'bad', 'entry', 'flags'))
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.disk.resolve() == args.output.resolve():
        parser.error('output must not overwrite input')
    result = build_fixture(args.disk.read_bytes(), args.variant)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)


if __name__ == '__main__':
    main()

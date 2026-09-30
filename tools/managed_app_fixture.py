#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable DOS-only managed-app faults; never modify boot payload sectors."""
from build_d71 import sector_offset


def dos_file(image, name):
    entries, seen = [], set()
    track, sector = 18, 1
    while track:
        pos = sector_offset(track, sector)
        if pos in seen or pos+256 > len(image):
            raise ValueError('invalid directory chain')
        seen.add(pos)
        for n in range(8):
            entry = pos+2+32*n
            if image[entry] == 0x81 and image[entry+3:entry+19].rstrip(b'\xa0') == name.encode():
                entries.append(entry)
        track, sector = image[pos:pos+2]
    if len(entries) != 1:
        raise ValueError('expected exactly one closed SEQ '+name)
    entry = entries[0]
    track, sector = image[entry+1:entry+3]
    offsets, seen = [], set()
    while track:
        pos = sector_offset(track, sector)
        if pos in seen or pos+256 > len(image):
            raise ValueError('invalid file chain')
        seen.add(pos)
        track, sector = image[pos:pos+2]
        count = 254 if track else sector-1
        if not 0 <= count <= 254:
            raise ValueError('invalid file byte count')
        offsets.extend(range(pos+2, pos+2+count))
    return entry, offsets


ERRORS = {'missing': 11, 'magic': 4, 'version': 5, 'cpu': 6, 'flags': 7,
          'slot': 8, 'entry': 10, 'size': 9, 'bss': 9, 'opcode': 10,
          'peer': 10, 'outside': 10, 'vector': 10}


def fixture(image, name, variant):
    entry, offsets = dos_file(image, name)
    result = bytearray(image)
    if variant == 'missing':
        result[entry] = 0
    else:
        base = 0x02 if name == 'XCLOCK' else 0x12
        peer = 0x12 if base == 2 else 2
        changes = {'magic': {0: 0}, 'version': {5: 2}, 'cpu': {6: 2},
                   'flags': {7: 0}, 'slot': {9: peer, 15: peer}, 'entry': {14: 1},
                   'size': {10: 0, 11: 0x0a}, 'bss': {12: 0xff, 13: 0xff},
                   'opcode': {16: 0x60}, 'peer': {17: 0, 18: peer},
                   'outside': {17: 0, 18: base+10}, 'vector': {17: 3, 18: base}}
        for index, value in changes[variant].items():
            result[offsets[index]] = value
    return bytes(result)

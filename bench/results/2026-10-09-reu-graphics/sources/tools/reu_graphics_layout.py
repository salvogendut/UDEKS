#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate the bank-0 hidden bitmap module and seal its boot-only delivery."""
import argparse
from pathlib import Path
from build_scheduler_overlay import map_segments

BASE, LIMIT, TRAILER = 0xd000, 0xe000, 0xdff0
SOURCE, SOURCE_LIMIT = 0x7300, 0x8300
BUFFER, BUFFER_LIMIT = 0x4180, 0x419e


def layout(segments):
    code, state, identity = (segments.get(n, (0, 0, 0)) for n in
                             ('BITMAPCODE', 'BITMAPSTATE', 'BITMAPID'))
    if (code[0] != BASE or not 0 < code[2] == code[1]-code[0]+1 or
            state[0] != code[1]+1 or not 0 < state[2] == state[1]-state[0]+1 or
            state[1] >= TRAILER or identity != (TRAILER, LIMIT-1, 16)):
        raise ValueError('hidden bitmap code/state/trailer exceeds physical bank-0 I/O RAM')
    return state


def seal(image, segments):
    state = layout(segments)
    if len(image) != 4096 or image[-16:] != b'RBMP\0\1'+bytes(10):
        raise ValueError('invalid unsealed hidden bitmap image')
    if any(image[state[0]-BASE:TRAILER-BASE]):
        raise ValueError('hidden bitmap BSS or padding is not zero initialized')
    result = bytearray(image)
    result[-10:-8] = (sum(image[:-16]) & 65535).to_bytes(2, 'little')
    return bytes(result)


def install(payload, image):
    if (len(image) != 4096 or image[-16:-10] != b'RBMP\0\1' or any(image[-8:]) or
            int.from_bytes(image[-10:-8], 'little') != sum(image[:-16]) & 65535):
        raise ValueError('invalid sealed bitmap image/checksum')
    if payload[:2] != b'\0\x12' or len(payload) != 2+0xe900-0x1200:
        raise ValueError('hidden bitmap delivery needs the complete secondary envelope')
    first = 2+SOURCE-0x1200
    if any(payload[first:first+4096]):
        raise ValueError('bitmap delivery overlaps another secondary payload')
    return payload[:first]+image+payload[first+4096:]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('image', type=Path)
    p.add_argument('map', type=Path)
    p.add_argument('panic_image', type=Path)
    p.add_argument('panic_map', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    normal, panic = map_segments(args.map.read_text()), map_segments(args.panic_map.read_text())
    if normal != panic or args.image.read_bytes() != args.panic_image.read_bytes():
        raise SystemExit('normal/panic hidden graphics layout or bytes disagree')
    args.output.write_bytes(seal(args.image.read_bytes(), normal))
    print('hidden bitmap: code/state fit; normal/panic parity; 4096-byte delivery sealed')


if __name__ == '__main__': main()

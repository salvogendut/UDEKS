#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Copy a native boot disk with KERNAL secondary-load messages enabled.

Only SETMSG's immediate operand changes. No loader, file allocation, kernel,
or secondary payload is replaced; the input disk is never overwritten.
"""
import argparse
from pathlib import Path
from build_d71 import boot_locations, sector_offset, PAYLOAD_BLOCKS


def diagnostic_image(source: bytes) -> bytes:
    address = 0x1FBB
    block, within = divmod(address - 0x1C00, 256)
    locations = list(boot_locations(1 + PAYLOAD_BLOCKS))
    offset = sector_offset(*locations[1 + block]) + within
    if source[offset:offset+5] != b'\xa9\x00\x20\x90\xff':
        raise ValueError('secondary loader SETMSG instruction differs; refusing to patch')
    image = bytearray(source)
    image[offset+1] = 0xff
    return bytes(image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disk', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.disk.resolve() == args.output.resolve():
        parser.error('diagnostic output must be a separate disk')
    args.output.write_bytes(diagnostic_image(args.disk.read_bytes()))


if __name__ == '__main__': main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Host model for a packed VIC window image; NOT installed in UDEKS.

The proposed bank-1 $4200-$5BFF cache is 6,656 bytes. This model proves the
bit shifts, edge masks, VIC row interleave and capacity before a gateway or
resident compositor ABI is designed. It makes no speed or ownership claim.
"""
import argparse
import json

WIDTH = 320
HEIGHT = 200
BITMAP_BYTES = 8000
CACHE_BASE = 0x4200
CACHE_LIMIT = 0x5C00
CACHE_BYTES = CACHE_LIMIT - CACHE_BASE


def byte_offset(byte_x, y):
    return (y & 248) * 40 + (y & 7) + byte_x * 8


def needed_bytes(width, height):
    return ((width + 7) // 8) * height


def valid_geometry(x, y, width, height):
    return (0 <= x < WIDTH and 0 <= y < HEIGHT and width > 0 and height > 0
            and x + width <= WIDTH and y + height <= HEIGHT
            and needed_bytes(width, height) <= CACHE_BYTES)


def capture(bitmap, x, y, width, height):
    if len(bitmap) != BITMAP_BYTES or not valid_geometry(x, y, width, height):
        raise ValueError('unsupported bitmap or cache geometry')
    stride = (width + 7) // 8
    shift = x & 7
    first_byte = x >> 3
    result = bytearray(needed_bytes(width, height))
    for row in range(height):
        for column in range(stride):
            source = first_byte + column
            left = bitmap[byte_offset(source, y + row)]
            if shift:
                right = bitmap[byte_offset(source + 1, y + row)] if source < 39 else 0
                value = ((left << shift) | (right >> (8 - shift))) & 255
            else:
                value = left
            if column == stride - 1 and width & 7:
                value &= (255 << (8 - (width & 7))) & 255
            result[row * stride + column] = value
    return bytes(result)


def paste(bitmap, image, x, y, width, height):
    if len(bitmap) != BITMAP_BYTES or not valid_geometry(x, y, width, height):
        raise ValueError('unsupported bitmap or cache geometry')
    if len(image) != needed_bytes(width, height):
        raise ValueError('cache image size mismatch')
    stride = (width + 7) // 8
    shift = x & 7
    first_byte = x >> 3
    for row in range(height):
        for column in range(stride):
            value = image[row * stride + column]
            valid = 255
            if column == stride - 1 and width & 7:
                valid = (255 << (8 - (width & 7))) & 255
            target = first_byte + column
            mask = valid >> shift
            index = byte_offset(target, y + row)
            bitmap[index] = (bitmap[index] & (~mask & 255)) | ((value >> shift) & mask)
            if shift and (valid << (8 - shift)) & 255:
                mask = (valid << (8 - shift)) & 255
                index = byte_offset(target + 1, y + row)
                bitmap[index] = (bitmap[index] & (~mask & 255)) | ((value << (8 - shift)) & mask)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width', type=int, default=168)
    parser.add_argument('--height', type=int, default=104)
    args = parser.parse_args()
    size = needed_bytes(args.width, args.height)
    print(json.dumps({'candidate_bank1_range': ['$4200', '$5BFF'],
                      'capacity_bytes': CACHE_BYTES,
                      'width': args.width, 'height': args.height,
                      'packed_stride': (args.width + 7) // 8,
                      'needed_bytes': size, 'fits': size <= CACHE_BYTES,
                      'status': 'host algorithm only; bank ownership and gateway unqualified'}, indent=2))


if __name__ == '__main__':
    main()

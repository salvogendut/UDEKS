#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert an 8-bit RGB/RGBA PNG into one 24x21 VIC-II hires sprite."""

from __future__ import annotations

import argparse
import binascii
import struct
import zlib
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SPRITE_WIDTH = 24
SPRITE_HEIGHT = 21
SPRITE_SIZE = 63


def paeth(left: int, above: int, upper_left: int) -> int:
    prediction = left + above - upper_left
    left_distance = abs(prediction - left)
    above_distance = abs(prediction - above)
    corner_distance = abs(prediction - upper_left)
    if left_distance <= above_distance and left_distance <= corner_distance:
        return left
    if above_distance <= corner_distance:
        return above
    return upper_left


def read_png_rgb(data: bytes) -> tuple[int, int, bytes]:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("input is not a PNG image")
    offset = len(PNG_SIGNATURE)
    header = None
    compressed = bytearray()
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        crc_end = payload_end + 4
        if crc_end > len(data):
            raise ValueError("PNG chunk is truncated")
        payload = data[payload_start:payload_end]
        expected_crc = struct.unpack_from(">I", data, payload_end)[0]
        actual_crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError("PNG chunk checksum is invalid")
        if kind == b"IHDR":
            if header is not None or length != 13:
                raise ValueError("PNG header is invalid")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
        offset = crc_end
    if header is None or not compressed:
        raise ValueError("PNG is missing image data")

    width, height, depth, color_type, compression, filtering, interlace = header
    if width == 0 or height == 0:
        raise ValueError("PNG dimensions are empty")
    if depth != 8 or color_type not in (2, 6):
        raise ValueError("PNG must use 8-bit RGB or RGBA pixels")
    if compression != 0 or filtering != 0 or interlace != 0:
        raise ValueError("PNG uses an unsupported encoding")

    channels = 3 if color_type == 2 else 4
    row_size = width * channels
    packed = zlib.decompress(bytes(compressed))
    expected_size = height * (row_size + 1)
    if len(packed) != expected_size:
        raise ValueError("PNG scanline data has an unexpected size")

    decoded = bytearray(height * row_size)
    source = 0
    for y in range(height):
        filter_type = packed[source]
        source += 1
        row_offset = y * row_size
        for x in range(row_size):
            raw = packed[source + x]
            left = decoded[row_offset + x - channels] if x >= channels else 0
            above = decoded[row_offset - row_size + x] if y != 0 else 0
            upper_left = (
                decoded[row_offset - row_size + x - channels]
                if y != 0 and x >= channels else 0
            )
            if filter_type == 0:
                value = raw
            elif filter_type == 1:
                value = raw + left
            elif filter_type == 2:
                value = raw + above
            elif filter_type == 3:
                value = raw + ((left + above) >> 1)
            elif filter_type == 4:
                value = raw + paeth(left, above, upper_left)
            else:
                raise ValueError(f"PNG uses unknown filter {filter_type}")
            decoded[row_offset + x] = value & 0xFF
        source += row_size

    if channels == 3:
        return width, height, bytes(decoded)
    rgb = bytearray(width * height * 3)
    destination = 0
    for source in range(0, len(decoded), 4):
        alpha = decoded[source + 3]
        for channel in range(3):
            value = decoded[source + channel]
            rgb[destination] = (
                value * alpha + 255 * (255 - alpha) + 127
            ) // 255
            destination += 1
    return width, height, bytes(rgb)


def sprite_bytes(width: int, height: int, rgb: bytes) -> bytes:
    if len(rgb) != width * height * 3:
        raise ValueError("RGB raster size does not match its dimensions")
    output = bytearray()
    for target_y in range(SPRITE_HEIGHT):
        y0 = target_y * height // SPRITE_HEIGHT
        y1 = (target_y + 1) * height // SPRITE_HEIGHT
        row = bytearray(3)
        for target_x in range(SPRITE_WIDTH):
            x0 = target_x * width // SPRITE_WIDTH
            x1 = (target_x + 1) * width // SPRITE_WIDTH
            brightness = 0
            samples = (x1 - x0) * (y1 - y0)
            for source_y in range(y0, y1):
                pixel = (source_y * width + x0) * 3
                for _ in range(x0, x1):
                    brightness += rgb[pixel] + rgb[pixel + 1] + rgb[pixel + 2]
                    pixel += 3
            if brightness < samples * 3 * 128:
                row[target_x >> 3] |= 0x80 >> (target_x & 7)
        output.extend(row)
    if len(output) != SPRITE_SIZE:
        raise AssertionError("VIC sprite encoder produced the wrong size")
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        width, height, rgb = read_png_rgb(args.input.read_bytes())
        sprite = sprite_bytes(width, height, rgb)
    except (OSError, ValueError, zlib.error) as error:
        raise SystemExit(f"cannot convert sprite: {error}") from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(sprite)


if __name__ == "__main__":
    main()

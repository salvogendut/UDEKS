#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert a JPEG/PNG into a UDEKS .CBM black-and-white picture.

.CBM is the Commodore BitMap container for the VIC-II hires display:
scanline-packed, one bit per pixel, MSB first, top-to-bottom. The viewer
streams these rows into a VIC window; the format is deliberately independent
of the 320x200 cell layout so the same file serves any width/height <= 320x200.
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PIL import Image

MAGIC = b"CBM\x00"
VERSION = 1
MAX_WIDTH = 320
MAX_HEIGHT = 200


def pack_bits(rows: list[list[int]]) -> bytes:
    """Pack 0/1 pixel rows into scanlines, MSB first, low bits zeroed."""
    if not rows:
        return b""
    if not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("pixel rows must have the same nonzero width")
    if any(pixel not in (0, 1) for row in rows for pixel in row):
        raise ValueError("pixels must be 0 or 1")
    stride = (len(rows[0]) + 7) // 8
    data = bytearray(len(rows) * stride)
    for y, row in enumerate(rows):
        for x, pixel in enumerate(row):
            if pixel:
                data[y * stride + x // 8] |= 0x80 >> (x % 8)
    return bytes(data)


def unpack_bits(data: bytes, width: int, height: int) -> list[list[int]]:
    """Expand scanline-packed .CBM payload bytes back into 0/1 pixel rows."""
    stride = (width + 7) // 8
    rows: list[list[int]] = []
    for y in range(height):
        row: list[int] = []
        for x in range(width):
            byte = data[y * stride + x // 8]
            row.append(1 if (byte & (0x80 >> (x % 8))) else 0)
        rows.append(row)
    return rows


def parse(data: bytes) -> tuple[int, int, list[list[int]]]:
    """Parse a complete .CBM file: (width, height, rows)."""
    if len(data) < 11 or data[:4] != MAGIC:
        raise ValueError("not a .CBM picture")
    if data[4] != VERSION:
        raise ValueError(f"unsupported .CBM version {data[4]}")
    width, height, stride = struct.unpack_from("<HHH", data, 5)
    if not 1 <= width <= MAX_WIDTH or not 1 <= height <= MAX_HEIGHT:
        raise ValueError("picture size out of range")
    if stride != (width + 7) // 8:
        raise ValueError("stride does not match width")
    payload = data[11:]
    if len(payload) != stride * height:
        raise ValueError("picture payload size does not match header")
    if width % 8:
        mask = (1 << (8 - width % 8)) - 1
        if any(payload[y * stride + stride - 1] & mask for y in range(height)):
            raise ValueError("nonzero row padding")
    return width, height, unpack_bits(payload, width, height)


def threshold_pixels(image: Image.Image, level: int, invert: bool,
                     dither: bool = False) -> list[list[int]]:
    gray = image.convert("L")
    if dither:
        gray = gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    rows: list[list[int]] = []
    for y in range(gray.height):
        row: list[int] = []
        for x in range(gray.width):
            value = gray.getpixel((x, y))
            bit = value < level
            if invert:
                bit = not bit
            row.append(1 if bit else 0)
        rows.append(row)
    return rows


def fit_resize(image: Image.Image, width: int, height: int) -> Image.Image:
    """Aspect-fit into width x height on a white canvas (hires B/W: 1=ink)."""
    # Transparent logo backgrounds must become paper, not black ink.
    rgba = image.convert("RGBA")
    paper = Image.new("RGBA", rgba.size, "white")
    paper.alpha_composite(rgba)
    image = paper.convert("L")
    scale = min(width / image.width, height / image.height)
    scaled = image.resize(
        (max(1, int(round(image.width * scale))), max(1, int(round(image.height * scale)))),
        Image.LANCZOS,
    )
    canvas = Image.new("L", (width, height), 255)
    offset = ((width - scaled.width) // 2, (height - scaled.height) // 2)
    canvas.paste(scaled, offset)
    return canvas


def build(data: bytes, width: int, height: int) -> bytes:
    if not 1 <= width <= MAX_WIDTH or not 1 <= height <= MAX_HEIGHT:
        raise ValueError("picture size out of range")
    stride = (width + 7) // 8
    expected = stride * height
    if len(data) != expected:
        raise ValueError(f".CBM bitmap is {len(data)} bytes, expected {expected}")
    header = MAGIC + bytes((VERSION,)) + struct.pack(
        "<HHH", width, height, stride)
    result = header + data
    parse(result)  # the writer enforces the same length and padding contract
    return result


def parse_number(text: str) -> int:
    return int(text, 0)


def convert(input_path: Path, output_path: Path, width: int, height: int,
            threshold: int, invert: bool, dither: bool = False) -> None:
    if not 1 <= width <= MAX_WIDTH or not 1 <= height <= MAX_HEIGHT:
        raise ValueError(f"picture size must be within {MAX_WIDTH}x{MAX_HEIGHT}")
    if not 0 <= threshold <= 255:
        raise ValueError("threshold must be in 0..255")
    if dither and threshold != 128:
        raise ValueError("--dither cannot be combined with a custom threshold")
    with Image.open(input_path) as image:
        canvas = fit_resize(image, width, height)
        rows = threshold_pixels(canvas, threshold, invert, dither)
    payload = pack_bits(rows)
    output_path.write_bytes(build(payload, width, height))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="source JPEG or PNG")
    parser.add_argument("output", type=Path, help="destination .CBM file")
    parser.add_argument("--width", type=parse_number, default=MAX_WIDTH,
                        help=f"picture width, 1..{MAX_WIDTH} (default {MAX_WIDTH})")
    parser.add_argument("--height", type=parse_number, default=MAX_HEIGHT,
                        help=f"picture height, 1..{MAX_HEIGHT} (default {MAX_HEIGHT})")
    parser.add_argument("--threshold", type=parse_number, default=128,
                        help="B/W threshold, 0..255 (default 128)")
    parser.add_argument("--invert", action="store_true",
                        help="invert black and white")
    parser.add_argument("--dither", action="store_true",
                        help="Floyd-Steinberg monochrome shading (instead of a custom threshold)")
    args = parser.parse_args()
    try:
        convert(args.input, args.output, args.width, args.height,
                args.threshold, args.invert, args.dither)
    except (OSError, ValueError) as error:
        parser.exit(2, f"cannot convert {args.input}: {error}\n")


if __name__ == "__main__":
    main()

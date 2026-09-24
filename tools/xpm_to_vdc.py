#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert a two-colour XPM image to row-major, MSB-first VDC bitmap bytes."""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from pathlib import Path


XPM_STRING = re.compile(r'^\s*("(?:\\.|[^"\\])*")')
RGB_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class XpmImage:
    width: int
    height: int
    rows: tuple[str, ...]
    colors: dict[str, tuple[int, int, int]]


def _strings(source: str) -> list[str]:
    values: list[str] = []
    for line in source.splitlines():
        match = XPM_STRING.match(line)
        if match is not None:
            values.append(ast.literal_eval(match.group(1)))
    return values


def parse_xpm(source: str) -> XpmImage:
    values = _strings(source)
    if not values:
        raise ValueError("XPM contains no string data")
    try:
        width, height, color_count, chars_per_pixel = map(
            int, values[0].split()[:4]
        )
    except (ValueError, IndexError) as error:
        raise ValueError("invalid XPM header") from error
    if width <= 0 or height <= 0 or color_count != 2 or chars_per_pixel <= 0:
        raise ValueError("VDC input must be a non-empty two-colour XPM")
    if len(values) != 1 + color_count + height:
        raise ValueError("XPM colour or row count does not match its header")

    colors: dict[str, tuple[int, int, int]] = {}
    for entry in values[1 : 1 + color_count]:
        symbol = entry[:chars_per_pixel]
        fields = entry[chars_per_pixel:].split()
        try:
            color_value = fields[fields.index("c") + 1]
        except (ValueError, IndexError) as error:
            raise ValueError(f"XPM colour {symbol!r} has no colour value") from error
        if not RGB_COLOR.fullmatch(color_value):
            raise ValueError("VDC input colours must use #RRGGBB notation")
        colors[symbol] = tuple(
            int(color_value[index : index + 2], 16) for index in (1, 3, 5)
        )
    if len(colors) != 2:
        raise ValueError("XPM colour symbols must be unique")

    rows = tuple(values[1 + color_count :])
    expected_width = width * chars_per_pixel
    if any(len(row) != expected_width for row in rows):
        raise ValueError("XPM row width does not match its header")
    if any(
        row[offset : offset + chars_per_pixel] not in colors
        for row in rows
        for offset in range(0, expected_width, chars_per_pixel)
    ):
        raise ValueError("XPM row uses an undefined colour symbol")
    return XpmImage(width, height, rows, colors)


def pack_vdc(image: XpmImage, dark_is_set: bool = True) -> bytes:
    chars_per_pixel = len(next(iter(image.colors)))
    ordered = sorted(
        image.colors,
        key=lambda symbol: sum(image.colors[symbol]),
    )
    set_symbol = ordered[0 if dark_is_set else 1]
    stride = (image.width + 7) // 8
    output = bytearray(image.height * stride)

    for y, row in enumerate(image.rows):
        for x in range(image.width):
            start = x * chars_per_pixel
            if row[start : start + chars_per_pixel] == set_symbol:
                output[y * stride + x // 8] |= 0x80 >> (x & 7)
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--light-is-set",
        action="store_true",
        help="encode the lighter colour as one bits instead of the darker colour",
    )
    args = parser.parse_args()

    try:
        image = parse_xpm(args.input.read_text(encoding="ascii"))
        packed = pack_vdc(image, dark_is_set=not args.light_is_set)
    except (OSError, UnicodeError, ValueError) as error:
        raise SystemExit(f"cannot convert XPM: {error}") from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(packed)
    stride = (image.width + 7) // 8
    print(
        f"packed {image.width}x{image.height} at {stride} bytes/row "
        f"into {len(packed)} bytes"
    )


if __name__ == "__main__":
    main()

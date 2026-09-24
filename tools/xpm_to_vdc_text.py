#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pack UDEKS logo tiles and UI glyphs for the VDC text console."""

from __future__ import annotations

import argparse
from pathlib import Path

from xpm_to_vdc import pack_vdc, parse_xpm


MAGIC = b"VTG1"
VERSION = 1
FIRST_CUSTOM_CODE = 0x80
BLANK_CODE = 0x20


def _tiles(source: Path) -> tuple[int, int, list[bytes]]:
    image = parse_xpm(source.read_text(encoding="ascii"))
    if image.width % 8 != 0:
        raise ValueError(f"{source}: width must be a multiple of eight")
    packed = pack_vdc(image)
    width = image.width // 8
    height = (image.height + 7) // 8
    tiles: list[bytes] = []
    for tile_y in range(height):
        for tile_x in range(width):
            rows = bytearray(8)
            for row in range(8):
                source_y = tile_y * 8 + row
                if source_y < image.height:
                    rows[row] = packed[source_y * width + tile_x]
            tiles.append(bytes(rows))
    return width, height, tiles


def _border_glyphs() -> tuple[bytes, ...]:
    vertical = 0x10
    return (
        bytes((0, 0, 0, 0, 0x1F, vertical, vertical, vertical)),
        bytes((0, 0, 0, 0, 0xF0, vertical, vertical, vertical)),
        bytes((vertical, vertical, vertical, vertical, 0x1F, 0, 0, 0)),
        bytes((vertical, vertical, vertical, vertical, 0xF0, 0, 0, 0)),
        bytes((0, 0, 0, 0, 0xFF, 0, 0, 0)),
        bytes((vertical,) * 8),
    )


def build_package(pipe_source: Path, wordmark_source: Path) -> bytes:
    pipe_width, pipe_height, pipe_tiles = _tiles(pipe_source)
    word_width, word_height, word_tiles = _tiles(wordmark_source)
    if max(pipe_width, pipe_height, word_width, word_height) > 255:
        raise ValueError("tile dimensions do not fit the package format")

    glyphs: list[bytes] = []
    codes: dict[bytes, int] = {}

    def code_for(tile: bytes) -> int:
        if tile == bytes(8):
            return BLANK_CODE
        if tile not in codes:
            code = FIRST_CUSTOM_CODE + len(glyphs)
            if code > 0xFF:
                raise ValueError("custom glyphs exceed the VDC screen-code range")
            codes[tile] = code
            glyphs.append(tile)
        return codes[tile]

    pipe_map = bytes(code_for(tile) for tile in pipe_tiles)
    word_map = bytes(code_for(tile) for tile in word_tiles)

    border_codes = []
    for glyph in _border_glyphs():
        border_codes.append(code_for(glyph))

    if len(glyphs) > 128:
        raise ValueError("custom glyphs would replace the stock lower character set")

    output = bytearray(MAGIC)
    output.extend(
        (
            VERSION,
            len(glyphs),
            pipe_width,
            pipe_height,
            word_width,
            word_height,
            *border_codes,
        )
    )
    for glyph in glyphs:
        output.extend(glyph)
        output.extend(bytes(8))
    output.extend(pipe_map)
    output.extend(word_map)
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pipe", type=Path)
    parser.add_argument("wordmark", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        package = build_package(args.pipe, args.wordmark)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(package)
    except (OSError, UnicodeError, ValueError) as error:
        raise SystemExit(f"cannot build VDC text assets: {error}") from error
    print(f"packed {package[5]} custom VDC glyphs into {len(package)} bytes")


if __name__ == "__main__":
    main()

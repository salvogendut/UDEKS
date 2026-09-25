#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS VIC-IIe graphics status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF1B0
RESULT_SIZE = 24


def word(block: bytes, offset: int) -> int:
    return block[offset] | (block[offset + 1] << 8)


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(
            f"VIC-graphics record is {len(data)} bytes; expected {RESULT_SIZE}"
        )
    block = data[:RESULT_SIZE]
    if block[:4] != b"VICG":
        raise ValueError("VIC-graphics status magic is not VICG")
    if block[4] != 1:
        raise ValueError(f"unsupported VIC-graphics format {block[4]}")
    if block[5] not in (2, 3):
        raise ValueError(f"VIC-graphics state is invalid ({block[5]:#04x})")
    if block[6] != 0:
        raise ValueError(f"VIC-graphics service reports error {block[6]:#04x}")
    if block[7:10] != b"\x01\x07\x00":
        raise ValueError("VIC mode or black-on-yellow colors are invalid")
    pointer_x = word(block, 10)
    pointer_y = block[12]
    if not 18 <= pointer_x <= 326 or not 45 <= pointer_y <= 234:
        raise ValueError("VIC pointer position is out of bounds")
    if block[13:17] != b"\x01\x60\x5c\xff":
        raise ValueError("VIC bank-1 memory layout is invalid")
    starts = word(block, 17)
    stops = word(block, 19)
    if block[5] == 3 and starts == 0:
        raise ValueError("active VIC graphics reports no initialization")
    if stops > starts:
        raise ValueError("VIC graphics has more stops than starts")
    if block[23] not in (0, 1, 2, 3):
        raise ValueError("VIC pointer shape state is invalid")
    return {
        "format": block[4],
        "state": block[5],
        "mode": block[7],
        "background": block[8],
        "pointer_color": block[9],
        "pointer_x": pointer_x,
        "pointer_y": pointer_y,
        "ram_bank": block[13],
        "bitmap_high": block[14],
        "screen_high": block[15],
        "sprite_pointer": block[16],
        "starts": starts,
        "stops": stops,
        "pointer_busy": block[23],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="VICG record, dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid VIC-graphics record: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
        return
    state = "active" if result["state"] == 3 else "ready"
    print(
        f"VIC-IIe graphics: {state}; {result['starts']} start(s), "
        f"{result['stops']} stop(s)"
    )


if __name__ == "__main__":
    main()

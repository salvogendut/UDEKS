#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate the UDEKS VIC-IIe window-manager status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF240
RESULT_SIZE = 32


def word(block: bytes, offset: int) -> int:
    return block[offset] | (block[offset + 1] << 8)


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError("window-manager record is truncated")
    block = data[:RESULT_SIZE]
    if block[:4] != b"WMGR" or block[4] != 1:
        raise ValueError("window-manager record magic or format is invalid")
    if block[5] != 2 or block[14] != 4 or block[15] != 0x0F:
        raise ValueError("window-manager state or capabilities are invalid")
    if block[6] > block[14]:
        raise ValueError("active window count exceeds capacity")
    if block[7] > block[14] or block[8] > block[14]:
        raise ValueError("window handle is outside the registry")
    if block[8] == 0 and any(block[9:13]):
        raise ValueError("idle manager publishes drag geometry")
    if block[8] != 0 and block[12] == 0:
        raise ValueError("dragging manager publishes an empty outline")
    return {
        "active": block[6],
        "focused": block[7],
        "dragging": block[8],
        "outline_x": word(block, 9),
        "outline_y": block[11],
        "outline_width": block[12],
        "creates": word(block, 16),
        "destroys": word(block, 18),
        "repaints": word(block, 20),
        "drag_moves": word(block, 22),
        "drag_starts": word(block, 24),
        "drag_finishes": word(block, 26),
        "close_requests": word(block, 28),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    block = extract_memory(
        args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
    )
    try:
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid window-manager record: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"window manager: {result['active']} active; "
            f"{result['repaints']} repaint(s); "
            f"{result['drag_finishes']} completed drag(s)"
        )


if __name__ == "__main__":
    main()

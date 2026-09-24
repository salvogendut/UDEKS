#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate the UDEKS xclock application status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF220
RESULT_SIZE = 32


def word(block: bytes, offset: int) -> int:
    return block[offset] | (block[offset + 1] << 8)


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError("xclock record is truncated")
    block = data[:RESULT_SIZE]
    if block[:4] != b"XCLK" or block[4] != 1:
        raise ValueError("xclock record magic or format is invalid")
    if block[5] not in (2, 3) or block[6] != 0:
        raise ValueError("xclock state is invalid")
    if block[7] != 7:
        raise ValueError("xclock capability flags are invalid")
    if block[10:12] != bytes((144, 154)):
        raise ValueError("xclock window dimensions are invalid")
    if block[8] + block[10] > 320 or block[9] + block[11] > 200:
        raise ValueError("xclock window lies outside the surface")
    if block[12] > 23 or block[13] > 59 or block[14] > 59:
        raise ValueError("xclock time is out of range")
    renders = word(block, 16)
    if block[5] == 3 and renders == 0:
        raise ValueError("running xclock has not rendered")
    return {
        "state": block[5],
        "x": block[8],
        "y": block[9],
        "width": block[10],
        "height": block[11],
        "hour": block[12],
        "minute": block[13],
        "second": block[14],
        "renders": renders,
        "ticks": word(block, 18),
        "moves": word(block, 20),
        "closes": word(block, 22),
        "dragging": block[24],
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
        raise SystemExit(f"invalid xclock record: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        state = "running" if result["state"] == 3 else "ready"
        print(
            f"xclock: {state}; {result['hour']:02d}:{result['minute']:02d}:"
            f"{result['second']:02d}; {result['renders']} repaint(s), "
            f"{result['ticks']} tick(s)"
        )


if __name__ == "__main__":
    main()

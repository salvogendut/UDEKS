#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate the UDEKS CIA time-service status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF200
RESULT_SIZE = 24


def word(block: bytes, offset: int) -> int:
    return block[offset] | (block[offset + 1] << 8)


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError("time record is truncated")
    block = data[:RESULT_SIZE]
    if block[:4] != b"TIME" or block[4] != 1:
        raise ValueError("time record magic or format is invalid")
    if block[5] != 2 or block[6] != 0 or block[7] != 1:
        raise ValueError("time service is not ready on CIA1 TOD")
    if block[8] > 23 or block[9] > 59 or block[10] > 59 or block[11] > 9:
        raise ValueError("published time is out of range")
    if block[20] not in (1, 2):
        raise ValueError("video timing standard is invalid")
    return {
        "hour": block[8],
        "minute": block[9],
        "second": block[10],
        "tenth": block[11],
        "polls": word(block, 16),
        "changes": word(block, 18),
        "video_standard": block[20],
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
        raise SystemExit(f"invalid time record: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"time: {result['hour']:02d}:{result['minute']:02d}:"
            f"{result['second']:02d}.{result['tenth']}; "
            f"{result['polls']} poll(s)"
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS root-terminal status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF150
RESULT_SIZE = 32


def word(block: bytes, offset: int) -> int:
    return block[offset] | (block[offset + 1] << 8)


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(
            f"root-terminal record is {len(data)} bytes; expected {RESULT_SIZE}"
        )
    block = data[:RESULT_SIZE]
    if block[:4] != b"RCLI":
        raise ValueError("root-terminal status magic is not RCLI")
    if block[4] != 1:
        raise ValueError(f"unsupported root-terminal format {block[4]}")
    if block[5] != 2:
        if block[5] & 0x80:
            raise ValueError(f"root terminal failed with code {block[6]:#04x}")
        raise ValueError(f"root-terminal state is {block[5]}, not ready")
    if block[6] != 0:
        raise ValueError(f"ready root terminal reports failure {block[6]:#04x}")
    if block[7] != 54:
        raise ValueError(f"line capacity is {block[7]}, expected 54")
    if block[8] > block[7] or block[9] > block[8]:
        raise ValueError("current line length or cursor is out of bounds")
    if block[10] not in (0, 1):
        raise ValueError("pending-refresh state is not Boolean")
    if block[20] > block[7]:
        raise ValueError("last submitted line exceeds capacity")
    return {
        "format": block[4],
        "state": block[5],
        "capacity": block[7],
        "length": block[8],
        "cursor": block[9],
        "pending_refresh": block[10],
        "focused_terminal": block[11],
        "polls": word(block, 12),
        "presses": word(block, 14),
        "edits": word(block, 16),
        "submissions": word(block, 18),
        "last_length": block[20],
        "last_checksum": word(block, 21),
        "overwrites": block[23],
        "refreshes": word(block, 24),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="terminal record, dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid root-terminal record: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        "Root terminal: ready "
        f"({result['length']}/{result['capacity']} characters, "
        f"cursor {result['cursor']})"
    )
    print(
        f"Input: {result['presses']} presses, {result['edits']} edits, "
        f"{result['submissions']} submissions; "
        f"{result['refreshes']} refreshes"
    )


if __name__ == "__main__":
    main()

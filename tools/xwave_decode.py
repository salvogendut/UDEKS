#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate the UDEKS xwave application status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF260
RESULT_SIZE = 32


def word(block: bytes, offset: int) -> int:
    return block[offset] | (block[offset + 1] << 8)


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError("xwave record is truncated")
    block = data[:RESULT_SIZE]
    if block[:4] != b"XWAV" or block[4] not in (1, 2, 3):
        raise ValueError("xwave record magic or format is invalid")
    if block[5] not in (2, 3) or block[6] != 0:
        raise ValueError("xwave state is invalid")
    if block[7] != 0x07:
        raise ValueError("xwave capability flags are invalid")
    if block[5] == 3:
        if block[22] < 48 or block[23] < 48:
            raise ValueError("running xwave has invalid window geometry")
        if block[20] + block[22] > 320 or block[21] + block[23] > 200:
            raise ValueError("xwave window lies outside the surface")
        if word(block, 16) == 0:
            raise ValueError("running xwave has not rendered")
        if block[4] == 2 and (
            block[9:12] != bytes((21, 25, 1)) or word(block, 18) != 525
        ):
            raise ValueError("running xwave surface geometry is invalid")
        if block[4] == 3 and (
            block[9:12] != bytes((21, 25, 2)) or word(block, 18) != 525
        ):
            raise ValueError("running xwave mesh geometry is invalid")
    return {
        "format": block[4],
        "state": block[5],
        "handle": block[8],
        "surface_rows": block[9] if block[4] >= 2 else 0,
        "surface_columns": block[10] if block[4] >= 2 else 0,
        "hidden_lines": block[11] if block[4] == 2 else 0,
        "mesh_axes": block[11] if block[4] >= 3 else 0,
        "z80_batches": word(block, 12),
        "fallback_batches": word(block, 14),
        "renders": word(block, 16),
        "samples": word(block, 18) if block[4] >= 2 else 0,
        "x": block[20],
        "y": block[21],
        "width": block[22],
        "height": block[23],
        "dragging": block[24],
        "focused": block[25],
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
        raise SystemExit(f"invalid xwave record: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        state = "running" if result["state"] == 3 else "ready"
        print(
            f"xwave: {state}; {result['renders']} repaint(s); "
            f"{result['z80_batches']} Z80 batch(es), "
            f"{result['fallback_batches']} fallback batch(es); "
            f"{result['samples']} surface sample(s)"
        )


if __name__ == "__main__":
    main()

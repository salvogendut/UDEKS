#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS pointer-input status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF1D0
RESULT_SIZE = 32


def word(block: bytes, offset: int) -> int:
    return block[offset] | (block[offset + 1] << 8)


def signed(byte: int) -> int:
    return byte - 256 if byte >= 128 else byte


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(
            f"pointer record is {len(data)} bytes; expected {RESULT_SIZE}"
        )
    block = data[:RESULT_SIZE]
    if block[:4] != b"PTRI":
        raise ValueError("pointer status magic is not PTRI")
    if block[4] != 1:
        raise ValueError(f"unsupported pointer format {block[4]}")
    if block[5] != 2 or block[6] != 0:
        raise ValueError(
            f"pointer service is not ready ({block[5]:#04x}/{block[6]:#04x})"
        )
    if block[7] != 0x0F:
        raise ValueError(f"pointer capability flags are invalid ({block[7]:#04x})")
    x = word(block, 8)
    y = block[10]
    if not 18 <= x <= 326 or not 45 <= y <= 234:
        raise ValueError(f"pointer position is out of bounds ({x}, {y})")
    return {
        "format": block[4],
        "state": block[5],
        "flags": block[7],
        "x": x,
        "y": y,
        "buttons": block[11],
        "joystick2": block[12],
        "mouse1_buttons": block[13],
        "mouse1_pot_x": block[14],
        "mouse1_pot_y": block[15],
        "dx": signed(block[16]),
        "dy": signed(block[17]),
        "samples": word(block, 18),
        "moves": word(block, 20),
        "mouse_events": word(block, 22),
        "joystick_events": word(block, 24),
        "sources": block[27],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="PTRI record, dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid pointer record: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        f"pointer: ({result['x']}, {result['y']}); "
        f"{result['samples']} IRQ sample(s), {result['moves']} move(s)"
    )


if __name__ == "__main__":
    main()

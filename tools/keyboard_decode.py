#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS keyboard-service status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF120
RESULT_SIZE = 48


def parse_result(data: bytes) -> dict[str, int | list[int]]:
    if len(data) < RESULT_SIZE:
        raise ValueError(
            f"keyboard record is {len(data)} bytes; expected {RESULT_SIZE}"
        )
    block = data[:RESULT_SIZE]
    if block[:4] != b"KEYB":
        raise ValueError("keyboard status magic is not KEYB")
    if block[4] != 1:
        raise ValueError(f"unsupported keyboard status format {block[4]}")
    if block[5] != 2:
        if block[5] & 0x80:
            raise ValueError(f"keyboard service failed with code {block[6]:#04x}")
        raise ValueError(f"keyboard state is {block[5]}, not ready")
    if block[6] != 0:
        raise ValueError(f"ready keyboard reports failure {block[6]:#04x}")
    if block[7] != 11 or block[8] != 16:
        raise ValueError(
            f"keyboard geometry is {block[7]} lines/{block[8]} events"
        )
    if block[9] > block[8]:
        raise ValueError("keyboard queue depth exceeds capacity")
    if block[15] not in (0, 1) or block[16] not in (0, 1):
        raise ValueError("keyboard switch state is not Boolean")
    if block[17] != 0x0F:
        raise ValueError(f"keyboard capability flags are {block[17]:#04x}")
    if block[11] not in (0, 1, 2):
        raise ValueError(f"invalid last-event type {block[11]}")
    if block[11] != 0 and block[12] >= 88:
        raise ValueError(f"invalid last scan code {block[12]}")
    return {
        "format": block[4],
        "state": block[5],
        "matrix_lines": block[7],
        "queue_capacity": block[8],
        "queue_depth": block[9],
        "dropped": block[10],
        "last_type": block[11],
        "last_scan_code": block[12],
        "last_character": block[13],
        "last_modifiers": block[14],
        "caps": block[15],
        "display_80": block[16],
        "flags": block[17],
        "polls": block[18] | (block[19] << 8),
        "presses": block[20] | (block[21] << 8),
        "releases": block[22] | (block[23] << 8),
        "matrix": list(block[24:35]),
        "last_press_scan_code": block[35],
        "last_press_character": block[36],
        "last_press_modifiers": block[37],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="keyboard record, dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid keyboard record: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
        return
    character = result["last_press_character"]
    shown = (
        "none"
        if result["presses"] == 0
        else repr(chr(character)) if character else "non-text"
    )
    print(
        "C128 keyboard: ready "
        f"({result['matrix_lines']} matrix lines, queue "
        f"{result['queue_depth']}/{result['queue_capacity']})"
    )
    print(
        f"Events: {result['presses']} press, {result['releases']} release, "
        f"{result['dropped']} dropped; last {shown}"
    )
    print(
        f"Switches: CAPS={result['caps']}, 80-column={result['display_80']}; "
        f"polls={result['polls']}"
    )


if __name__ == "__main__":
    main()

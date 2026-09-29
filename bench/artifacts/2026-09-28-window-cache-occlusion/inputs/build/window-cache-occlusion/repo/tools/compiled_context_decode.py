#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the compiled-C context-switch result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF1A0
RESULT_SIZE = 32


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"result block is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"UCCS":
        raise ValueError("compiled-context magic is not UCCS")
    if block[4] != 1:
        raise ValueError(f"unsupported compiled-context format {block[4]}")
    if block[5] != 1:
        raise ValueError(f"unknown CPU identifier {block[5]}")
    if block[6] != 2:
        if block[6] & 0x80:
            raise ValueError(f"compiled-context failure {block[7]}")
        raise ValueError(f"compiled-context state is {block[6]}, not complete")
    if block[7] != 0:
        raise ValueError(f"complete run reports failure {block[7]}")
    switches = block[8] | (block[9] << 8)
    if switches != 64:
        raise ValueError(f"switch count is {switches}, expected 64")
    if block[10:12] != b"\x20\x20":
        raise ValueError(f"task steps are {block[10]}/{block[11]}, expected 32/32")
    sum_a = block[12] | (block[13] << 8)
    sum_b = block[14] | (block[15] << 8)
    if (sum_a, sum_b) != (0x1444, 0x4741):
        raise ValueError(f"task sums are ${sum_a:04X}/${sum_b:04X}")
    if block[16] != 2:
        raise ValueError(f"strategy {block[16]} is not relocation")
    if block[17] != 3:
        raise ValueError(f"completion mask is {block[17]:#04x}, expected 0x03")
    sp_a = block[18] | (block[19] << 8)
    sp_b = block[20] | (block[21] << 8)
    if (sp_a, sp_b) != (0x70F0, 0x71F0):
        raise ValueError(f"software stacks restored to ${sp_a:04X}/${sp_b:04X}")
    if any(block[22:]):
        raise ValueError("unused result bytes 22-31 are nonzero")
    return {
        "format": block[4],
        "cpu": block[5],
        "state": block[6],
        "failure": block[7],
        "switches": switches,
        "step_a": block[10],
        "step_b": block[11],
        "sum_a": sum_a,
        "sum_b": sum_b,
        "strategy": block[16],
        "done_mask": block[17],
        "software_stack_a": sp_a,
        "software_stack_b": sp_b,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid compiled-context record: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        "Compiled context: relocation complete "
        f"({result['switches']} switches, tasks "
        f"{result['step_a']}/{result['step_b']})"
    )
    print(
        f"C sums: ${result['sum_a']:04X}/${result['sum_b']:04X}; "
        f"software stacks: ${result['software_stack_a']:04X}/"
        f"${result['software_stack_b']:04X}"
    )


if __name__ == "__main__":
    main()

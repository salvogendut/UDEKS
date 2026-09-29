#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS 8502 clock status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF100
RESULT_SIZE = 16


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"clock record is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"CLK2":
        raise ValueError("clock status magic is not CLK2")
    if block[4] != 1:
        raise ValueError(f"unsupported clock status format {block[4]}")
    if block[5] != 2:
        if block[5] & 0x80:
            raise ValueError(f"clock transition failed with code {block[6]:#04x}")
        raise ValueError(f"clock state is {block[5]}, not ready")
    if block[6] != 0:
        raise ValueError("ready clock record reports a failure")
    if block[11] != 2:
        raise ValueError(f"requested clock is {block[11]} MHz, not 2 MHz")
    if block[8] & 0x03 != 0x01:
        raise ValueError(f"invalid $D030 readback {block[8]:#04x}")
    if block[10] & 0x10:
        raise ValueError(f"VIC display remains enabled in $D011 {block[10]:#04x}")
    if block[12] & 0x07 != 0x07:
        raise ValueError(f"incomplete clock flags {block[12]:#04x}")
    return {
        "format": block[4],
        "state": block[5],
        "failure": block[6],
        "d030_before": block[7],
        "d030_after": block[8],
        "d011_before": block[9],
        "d011_after": block[10],
        "requested_mhz": block[11],
        "flags": block[12],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="clock record, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid clock record: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        "8502 clock: "
        f"{result['requested_mhz']} MHz ready "
        f"($D030 {result['d030_before']:#04x}->{result['d030_after']:#04x}, "
        f"$D011 {result['d011_before']:#04x}->{result['d011_after']:#04x})"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS 8502 panic record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF0B0
RESULT_SIZE = 16


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"panic record is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"PANI":
        raise ValueError("panic status magic is not PANI")
    if block[4] != 1:
        raise ValueError(f"unsupported panic status format {block[4]}")
    if block[5] != 2:
        raise ValueError(f"panic record state is {block[5]}, not published")
    if block[6] == 0:
        raise ValueError("panic code is zero")
    if block[7] != 0:
        raise ValueError(f"panic CPU is {block[7]}, expected 8502 (0)")
    if not block[8] & 0x04:
        raise ValueError("panic processor status does not have IRQ masking set")
    if block[9] != 0x3E:
        raise ValueError(f"panic MMU configuration is {block[9]:#04x}, expected 0x3e")
    if not block[10] & 0x01 or block[10] & 0x40:
        raise ValueError(f"panic mode {block[10]:#04x} is not 8502 C128 mode")
    if block[11] != 0x03:
        raise ValueError(f"panic VDC flags are {block[11]:#04x}, expected 0x03")
    if any(block[12:16]):
        raise ValueError("reserved panic bytes are nonzero")
    return {
        "format": block[4],
        "state": block[5],
        "code": block[6],
        "cpu": block[7],
        "processor_status": block[8],
        "mmu_configuration": block[9],
        "mode": block[10],
        "vdc_flags": block[11],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="panic record, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid panic record: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"8502 panic: code 0x{result['code']:02x}")
    print("Diagnostic record published; VDC panic text completed")


if __name__ == "__main__":
    main()

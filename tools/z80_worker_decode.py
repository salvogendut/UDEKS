#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS bounded-Z80-worker record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF190
RESULT_SIZE = 32


def word(block: bytes, offset: int) -> int:
    return block[offset] | (block[offset + 1] << 8)


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(
            f"Z80-worker record is {len(data)} bytes; expected {RESULT_SIZE}"
        )
    block = data[:RESULT_SIZE]
    if block[:4] != b"ZWRK":
        raise ValueError("Z80-worker status magic is not ZWRK")
    if block[4] != 1:
        raise ValueError(f"unsupported Z80-worker format {block[4]}")
    if block[5] != 2:
        if block[5] == 0:
            raise ValueError(f"Z80 worker is offline with code {block[6]:#04x}")
        raise ValueError(f"Z80 worker is not ready (state {block[5]:#04x})")
    if block[6] != 0 or block[10] != 0 or block[11] != 0:
        raise ValueError("ready Z80 worker reports a service or mailbox failure")
    if block[16:18] != b"\x00\x02":
        raise ValueError("Z80 worker does not report mailbox ABI 0.2")
    if block[18:21] != b"\x01\x01\x01":
        raise ValueError("Z80 image, gateway, or stock-timing policy is missing")
    if block[21] != 3:
        raise ValueError("last Z80 transaction did not complete")
    transactions = word(block, 12)
    if transactions == 0:
        raise ValueError("ready Z80 worker has completed no transactions")
    return {
        "format": block[4],
        "state": block[5],
        "last_opcode": block[7],
        "sequence": word(block, 8),
        "transactions": transactions,
        "failures": word(block, 14),
        "abi_major": block[16],
        "abi_minor": block[17],
        "stock_timing": block[20],
        "last_state": block[21],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="worker record, dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid Z80-worker record: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        "Z80 worker: ready at stock timing; "
        f"{result['transactions']} transaction(s), sequence {result['sequence']}"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate the UDEKS native-memory bootstrap status block."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


STATUS_BASE = 0xF040
STATUS_SIZE = 16


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < STATUS_SIZE:
        raise ValueError(f"status block is {len(data)} bytes; expected {STATUS_SIZE}")
    block = data[:STATUS_SIZE]
    if block[:4] != b"UMMU":
        raise ValueError("bootstrap status magic is not UMMU")
    if block[4] != 1:
        raise ValueError(f"unsupported bootstrap status format {block[4]}")
    if block[5] != 2:
        raise ValueError(f"bootstrap state is {block[5]}, not complete")
    if block[6] != 0x3E:
        raise ValueError(f"MMU configuration is {block[6]:#04x}, expected 0x3e")
    if block[7] & 0x4F != 0x09:
        raise ValueError(
            f"RAM configuration is {block[7]:#04x}; expected top 4K common "
            "with VIC bank 0"
        )
    if block[8] != 0 or block[9] & 1:
        raise ValueError("page zero is not physical bank-0 page 0")
    if block[10] != 1 or block[11] & 1:
        raise ValueError("page one is not physical bank-0 page 1")
    if not block[12] & 0x01 or block[12] & 0x40:
        raise ValueError(f"mode register {block[12]:#04x} is not 8502 C128 mode")
    return {
        "format": block[4],
        "state": block[5],
        "configuration": block[6],
        "ram_configuration": block[7],
        "page0_page": block[8],
        "page0_bank": block[9] & 1,
        "page1_page": block[10],
        "page1_bank": block[11] & 1,
        "mode": block[12],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="status block, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), STATUS_BASE, STATUS_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid bootstrap status: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print("Bootstrap MMU state: complete")
    print(f"Configuration: 0x{result['configuration']:02x}")
    print(f"RAM configuration: 0x{result['ram_configuration']:02x}")
    print(
        f"Page zero: bank {result['page0_bank']}, page 0x{result['page0_page']:02x}"
    )
    print(
        f"Page one: bank {result['page1_bank']}, page 0x{result['page1_page']:02x}"
    )
    print(f"Mode: 0x{result['mode']:02x}")


if __name__ == "__main__":
    main()

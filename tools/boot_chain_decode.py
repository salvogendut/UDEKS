#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the complete UDEKS native D71 boot chain."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number
from boot_status_decode import parse_result as parse_boot_status


RESULT_BASE = 0xF040
RESULT_SIZE = 48
CHAIN_OFFSET = 16


def parse_result(data: bytes) -> dict[str, int | dict[str, int]]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"boot record is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    kernel = parse_boot_status(block[:16])
    chain = block[CHAIN_OFFSET:]
    if chain[:4] != b"S0OK":
        raise ValueError("stage-0 completion marker is missing")
    if chain[4:8] != b"S1OK":
        raise ValueError("stage-1 completion marker is missing")
    if chain[8:12] != b"Z80!":
        raise ValueError("Z80 installation marker is missing")
    if chain[12] != 2:
        if chain[12] & 0x80:
            raise ValueError(
                f"native loader failed with code {chain[13]:#04x}"
            )
        raise ValueError(f"native loader state is {chain[12]}, not complete")
    if chain[13] != 0:
        raise ValueError(f"native loader failure code is {chain[13]:#04x}")
    source_sum = int.from_bytes(chain[14:16], "little")
    destination_sum = int.from_bytes(chain[16:18], "little")
    if source_sum != destination_sum:
        raise ValueError(
            f"Z80 checksum mismatch: source {source_sum:#06x}, "
            f"destination {destination_sum:#06x}"
        )
    if chain[18] != 0xD4:
        raise ValueError(f"loader reports {chain[18]} blocks; expected 212")
    if chain[19] != 1:
        raise ValueError(f"unsupported native loader format {chain[19]}")
    return {
        "kernel": kernel,
        "loader_state": chain[12],
        "loader_failure": chain[13],
        "z80_checksum": source_sum,
        "blocks": chain[18],
        "loader_format": chain[19],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="boot record, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid native boot record: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print("Native D71 boot: stage 0 -> stage 1 -> 8502 kernel complete")
    print(f"Z80 image: installed and verified (checksum 0x{result['z80_checksum']:04x})")
    print(f"Raw payload: {result['blocks']} sectors")


if __name__ == "__main__":
    main()

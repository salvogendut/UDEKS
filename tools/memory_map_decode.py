#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the native MMU profile/relocation probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF100
RESULT_SIZE = 128
EXPECTED_OBSERVATIONS = bytes(
    (
        0x3E, 0x09, 0x01, 0x3F, 0xD0, 0x7F, 0xD1, 0x7E,
        0x7E, 0xA1, 0xA0, 0xD0, 0x3E, 0x5C, 0x5A, 0xA5,
        0x6B, 0xB6, 0x3E, 0x00, 0x00, 0x01, 0x00,
    )
)


def parse_result(data: bytes) -> dict[str, int | list[int]]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"result block is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"MAPQ":
        raise ValueError("memory-map result magic is not MAPQ")
    if block[4] != 1:
        raise ValueError(f"unsupported memory-map result format {block[4]}")
    if block[5] != 2:
        if block[5] & 0x80:
            raise ValueError(
                f"probe failed at check {block[5] & 0x7f:#04x}: "
                f"expected {block[10]:#04x}, got {block[11]:#04x}"
            )
        raise ValueError(f"probe state is {block[5]}, not complete")
    if block[6] != 23 or block[7] != 23:
        raise ValueError(f"probe passed {block[7]} of {block[6]} checks; expected 23")
    if block[8] != 0:
        raise ValueError(f"probe failure code is {block[8]:#04x}")
    if block[9] != 0:
        raise ValueError(f"probe stopped in MMU profile {block[9]}")
    observations = block[16 : 16 + len(EXPECTED_OBSERVATIONS)]
    if observations != EXPECTED_OBSERVATIONS:
        for index, (actual, expected) in enumerate(
            zip(observations, EXPECTED_OBSERVATIONS, strict=True)
        ):
            if actual != expected:
                raise ValueError(
                    f"observation {index} is {actual:#04x}; expected {expected:#04x}"
                )
    return {
        "format": block[4],
        "state": block[5],
        "tests": block[6],
        "passed": block[7],
        "failure": block[8],
        "profile": block[9],
        "observations": list(observations),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="result block, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid memory-map result: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"Native MMU probe: {result['passed']}/{result['tests']} checks passed")
    print("Profiles: kernel I/O, kernel flat, worker I/O, worker flat")
    print("Page relocation: bank-1 pages 0x80/0x81 verified")


if __name__ == "__main__":
    main()

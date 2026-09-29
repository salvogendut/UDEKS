#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS task-state diagnostic record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF110
RESULT_SIZE = 16
MAX_TASKS = 8


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"task-state record is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"UTSK":
        raise ValueError("task-state magic is not UTSK")
    if block[4] != 0 or block[5] != 1:
        raise ValueError(
            f"unexpected task ABI {block[4]}.{block[5]}; expected 0.1"
        )
    if block[6] != 1:
        if block[6] & 0x80:
            raise ValueError(f"task table failed with code {block[6] & 0x7F}")
        raise ValueError("task table is uninitialized")
    if block[15] != 0:
        raise ValueError(f"reserved task-state byte is {block[15]:#04x}")
    if block[9] > MAX_TASKS:
        raise ValueError(
            f"defined count {block[9]} exceeds the table capacity {MAX_TASKS}"
        )
    if block[8] > block[9]:
        raise ValueError(
            f"runnable count {block[8]} exceeds defined count {block[9]}"
        )
    if block[7] > MAX_TASKS:
        raise ValueError(f"current task id {block[7]} is outside the table")
    if block[7] != 0 and block[8] == 0:
        raise ValueError("a current task is reported with no runnable tasks")
    return {
        "abi_major": block[4],
        "abi_minor": block[5],
        "state": block[6],
        "current": block[7],
        "runnable": block[8],
        "defined": block[9],
        "rejected": block[10],
        "canary": block[11],
        "switches": block[12] | (block[13] << 8),
        "last_event": block[14],
        "reserved": block[15],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="task-state record, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid task-state record: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        "Task table: ready "
        f"({result['defined']} defined, {result['runnable']} runnable, "
        f"ABI {result['abi_major']}.{result['abi_minor']})"
    )
    print(
        f"Dispatch: current={result['current']}, "
        f"switches={result['switches']}, "
        f"rejected={result['rejected']}, canary={result['canary']}"
    )


if __name__ == "__main__":
    main()

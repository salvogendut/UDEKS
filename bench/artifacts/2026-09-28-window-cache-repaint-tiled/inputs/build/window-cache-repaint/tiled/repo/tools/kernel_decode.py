#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate an UDEKS kernel-primitives benchmark result block."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory


RESULT_BASE = 0xF180
RESULT_SIZE = 128
HEADER_SIZE = 16
RECORD_SIZE = 8
CPU_NAMES = {1: "8502", 2: "z80"}
CASE_NAMES = {
    1: "empty",
    2: "switch_dispatch",
    3: "table_dispatch",
    4: "event_queue",
    5: "mmu_access",
    6: "cia_access",
    7: "vdc_access",
}


def expected_checksums() -> dict[int, int]:
    state = 0x1357
    for index in range(128):
        selector = (state ^ index) & 3
        if selector == 0:
            state = (state + 0x0101) & 0xFFFF
        elif selector == 1:
            state ^= 0x5A5A
        elif selector == 2:
            state = ((state >> 1) | (state << 15)) & 0xFFFF
        else:
            state = (state - 0x001D) & 0xFFFF

    event_sum = 0
    for serial in range(32):
        event_sum = (
            event_sum + serial + (serial ^ 0x5A) + 0x1200 + serial
        ) & 0xFFFF
    return {
        1: 0xBEEF,
        2: state,
        3: state,
        4: event_sum,
        5: 128,
        6: 128,
        7: 128,
    }


def parse_result(data: bytes) -> dict[str, object]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"result block is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"KPRM":
        raise ValueError("kernel-benchmark magic is not KPRM")
    if block[4] != 1:
        raise ValueError(f"unsupported kernel-benchmark format {block[4]}")
    cpu_id = block[5]
    if cpu_id not in CPU_NAMES:
        raise ValueError(f"unknown CPU identifier {cpu_id}")
    configuration = block[6]
    if cpu_id == 1 and configuration not in (1, 2):
        raise ValueError(f"8502 configuration identifier is {configuration}")
    if cpu_id == 2 and configuration != 3:
        raise ValueError(f"Z80 configuration identifier is {configuration}")
    if block[7] != len(CASE_NAMES):
        raise ValueError(f"case count is {block[7]}, expected {len(CASE_NAMES)}")
    if block[8] != 2:
        raise ValueError(f"benchmark state is {block[8]}, not complete")
    if block[9] != RECORD_SIZE:
        raise ValueError(f"record size is {block[9]}, expected {RECORD_SIZE}")
    if block[10] != 1:
        raise ValueError(f"unknown timer identifier {block[10]}")

    expected = expected_checksums()
    records = []
    seen = set()
    for index in range(block[7]):
        offset = HEADER_SIZE + index * RECORD_SIZE
        case_id = block[offset]
        status = block[offset + 1]
        iterations = int.from_bytes(block[offset + 2 : offset + 4], "little")
        ticks = int.from_bytes(block[offset + 4 : offset + 6], "little")
        checksum = int.from_bytes(block[offset + 6 : offset + 8], "little")
        if case_id not in CASE_NAMES:
            raise ValueError(f"record {index} has unknown case {case_id}")
        if case_id in seen:
            raise ValueError(f"duplicate case {case_id}")
        if status:
            raise ValueError(f"case {CASE_NAMES[case_id]} has status {status}")
        if ticks == 0xFFFF:
            raise ValueError(f"case {CASE_NAMES[case_id]} overflowed the timer")
        if checksum != expected[case_id]:
            raise ValueError(
                f"case {CASE_NAMES[case_id]} checksum is {checksum:#06x}; "
                f"expected {expected[case_id]:#06x}"
            )
        seen.add(case_id)
        records.append(
            {
                "id": case_id,
                "name": CASE_NAMES[case_id],
                "iterations": iterations,
                "ticks": ticks,
                "checksum": checksum,
            }
        )

    return {
        "format": block[4],
        "cpu": CPU_NAMES[cpu_id],
        "configuration": configuration,
        "timer": "cia1-timer-b",
        "records": records,
    }


def parse_number(value: str) -> int:
    return int(value, 0)


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
        raise SystemExit(f"invalid kernel-benchmark result: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"CPU: {result['cpu']}")
    print(f"Configuration: {result['configuration']}")
    print("case                 iterations    ticks  checksum")
    for record in result["records"]:
        print(
            f"{record['name']:<21} {record['iterations']:>10} "
            f"{record['ticks']:>8}  0x{record['checksum']:04x}"
        )


if __name__ == "__main__":
    main()

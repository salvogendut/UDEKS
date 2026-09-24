#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate the UDEKS bidirectional CPU-handoff benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory


RESULT_BASE = 0xF180
RESULT_SIZE = 64
HEADER_SIZE = 16
RECORD_SIZE = 8
CASE_NAMES = {
    1: "8502_to_z80_bare",
    2: "8502_to_z80_mailbox",
    3: "z80_to_8502_bare",
    4: "z80_to_8502_mailbox",
}
ERROR_NAMES = {
    0: "none",
    1: "phase",
    2: "mailbox",
    3: "response",
    4: "timer-overflow",
    5: "peer-count",
}


def parse_result(data: bytes) -> dict[str, object]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"result block is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"HNDF":
        raise ValueError("handoff-benchmark magic is not HNDF")
    if block[4] != 1:
        raise ValueError(f"unsupported handoff-benchmark format {block[4]}")
    if block[5] != 2:
        error = ERROR_NAMES.get(block[11], f"unknown-{block[11]}")
        raise ValueError(f"benchmark state is {block[5]:#04x}, not complete ({error})")
    if block[6] != len(CASE_NAMES):
        raise ValueError(f"case count is {block[6]}, expected {len(CASE_NAMES)}")
    if block[7] != RECORD_SIZE:
        raise ValueError(f"record size is {block[7]}, expected {RECORD_SIZE}")
    iterations = int.from_bytes(block[8:10], "little")
    if iterations != 64:
        raise ValueError(f"iteration count is {iterations}, expected 64")
    if block[10] != 1:
        raise ValueError(f"unknown timer identifier {block[10]}")
    if block[11]:
        raise ValueError(f"completed result retains error code {block[11]}")
    if block[12] not in (1, 2):
        raise ValueError(f"unknown 8502 speed identifier {block[12]}")

    records = []
    seen = set()
    for index in range(block[6]):
        offset = HEADER_SIZE + index * RECORD_SIZE
        case_id = block[offset]
        status = block[offset + 1]
        record_iterations = int.from_bytes(block[offset + 2 : offset + 4], "little")
        ticks = int.from_bytes(block[offset + 4 : offset + 6], "little")
        checksum = int.from_bytes(block[offset + 6 : offset + 8], "little")
        if case_id not in CASE_NAMES:
            raise ValueError(f"record {index} has unknown case {case_id}")
        if case_id in seen:
            raise ValueError(f"duplicate case {case_id}")
        if status:
            raise ValueError(f"case {CASE_NAMES[case_id]} has status {status}")
        if record_iterations != iterations:
            raise ValueError(
                f"case {CASE_NAMES[case_id]} has {record_iterations} iterations; "
                f"expected {iterations}"
            )
        if ticks in (0, 0xFFFF):
            raise ValueError(f"case {CASE_NAMES[case_id]} has invalid ticks {ticks:#06x}")
        if checksum != iterations:
            raise ValueError(
                f"case {CASE_NAMES[case_id]} peer count is {checksum}; "
                f"expected {iterations}"
            )
        seen.add(case_id)
        records.append(
            {
                "id": case_id,
                "name": CASE_NAMES[case_id],
                "iterations": record_iterations,
                "ticks": ticks,
                "ticks_per_round_trip": ticks / record_iterations,
                "peer_count": checksum,
            }
        )

    by_id = {record["id"]: record for record in records}
    overhead = {
        "8502_requester_ticks": by_id[2]["ticks"] - by_id[1]["ticks"],
        "z80_requester_ticks": by_id[4]["ticks"] - by_id[3]["ticks"],
    }
    overhead["8502_requester_ticks_per_transaction"] = (
        overhead["8502_requester_ticks"] / iterations
    )
    overhead["z80_requester_ticks_per_transaction"] = (
        overhead["z80_requester_ticks"] / iterations
    )

    return {
        "format": block[4],
        "8502_mhz": block[12],
        "z80_timing_requirement": "stock-2-tstates-per-system-tick-not-encoded",
        "timer": "cia1-timer-b",
        "records": records,
        "mailbox_overhead": overhead,
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
        raise SystemExit(f"invalid handoff-benchmark result: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"8502 speed: {result['8502_mhz']} MHz")
    print(f"Z80 timing requirement: {result['z80_timing_requirement']}")
    print("case                       iterations    ticks  ticks/round-trip")
    for record in result["records"]:
        print(
            f"{record['name']:<27} {record['iterations']:>10} "
            f"{record['ticks']:>8}  {record['ticks_per_round_trip']:>16.3f}"
        )
    print("Mailbox cost above bare round trip:")
    print(
        "  8502 requester: "
        f"{result['mailbox_overhead']['8502_requester_ticks_per_transaction']:.3f} ticks"
    )
    print(
        "  Z80 requester:  "
        f"{result['mailbox_overhead']['z80_requester_ticks_per_transaction']:.3f} ticks"
    )


if __name__ == "__main__":
    main()

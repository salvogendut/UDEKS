#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate the UDEKS dual-CPU offload crossover sweep."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory


RESULT_BASE = 0xF400
RESULT_SIZE = 416
HEADER_SIZE = 32
RECORD_SIZE = 16
SIZES = (16, 32, 64, 128, 256, 512, 1024, 2048)
OP_NAMES = {1: "copy", 2: "checksum16", 3: "transform"}
ERROR_NAMES = {
    0: "none",
    1: "phase",
    2: "mailbox",
    3: "response",
    4: "timer-overflow",
    5: "validation",
    6: "result-layout",
}


def expected_checksums() -> dict[int, tuple[int, ...]]:
    source = bytes((index * 37 + 11) & 0xFF for index in range(max(SIZES)))
    transformed = bytes(
        (((value ^ 0xA5) << 1) | ((value ^ 0xA5) >> 7)) & 0xFF
        for value in source
    )
    source_sums = tuple(sum(source[:size]) & 0xFFFF for size in SIZES)
    transform_sums = tuple(sum(transformed[:size]) & 0xFFFF for size in SIZES)
    return {1: source_sums, 2: source_sums, 3: transform_sums}


def _first_crossover(records: list[dict[str, object]], local: str, offload: str):
    for record in records:
        if record[offload] < record[local]:
            return {
                "size": record["size"],
                "local_ticks": record[local],
                "offload_ticks": record[offload],
            }
    return None


def parse_result(data: bytes) -> dict[str, object]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"result block is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"XOFS":
        raise ValueError("offload-benchmark magic is not XOFS")
    if block[4] != 1:
        raise ValueError(f"unsupported offload-benchmark format {block[4]}")
    if block[5] != 2:
        error = ERROR_NAMES.get(block[11], f"unknown-{block[11]}")
        raise ValueError(f"benchmark state is {block[5]:#04x}, not complete ({error})")
    if block[6] != len(OP_NAMES):
        raise ValueError(f"operation count is {block[6]}, expected {len(OP_NAMES)}")
    if block[7] != len(SIZES):
        raise ValueError(f"size count is {block[7]}, expected {len(SIZES)}")
    if block[8] != RECORD_SIZE:
        raise ValueError(f"record size is {block[8]}, expected {RECORD_SIZE}")
    if block[9] != 1:
        raise ValueError(f"unknown timer identifier {block[9]}")
    if block[10] not in (1, 2):
        raise ValueError(f"unknown 8502 speed identifier {block[10]}")
    if block[11]:
        raise ValueError(f"completed result retains error code {block[11]}")
    expected_count = len(OP_NAMES) * len(SIZES)
    if block[12] != expected_count:
        raise ValueError(f"record count is {block[12]}, expected {expected_count}")
    if block[13:16] != bytes((0xC0, 0xC8, 0x08)):
        raise ValueError("buffer-layout metadata is not C000/C800/0800")

    expected = expected_checksums()
    records = []
    for index in range(expected_count):
        offset = HEADER_SIZE + index * RECORD_SIZE
        op_id = block[offset]
        validation = block[offset + 1]
        size = int.from_bytes(block[offset + 2 : offset + 4], "little")
        expected_op = index // len(SIZES) + 1
        size_index = index % len(SIZES)
        if op_id != expected_op:
            raise ValueError(
                f"record {index} operation is {op_id}, expected {expected_op}"
            )
        if size != SIZES[size_index]:
            raise ValueError(
                f"record {index} size is {size}, expected {SIZES[size_index]}"
            )
        if validation != 0x0F:
            raise ValueError(
                f"{OP_NAMES[op_id]} {size}-byte validation mask is "
                f"{validation:#04x}, expected 0x0f"
            )

        tick_names = (
            "local_8502_ticks",
            "offload_to_z80_ticks",
            "local_z80_ticks",
            "offload_to_8502_ticks",
        )
        ticks = {}
        for tick_index, name in enumerate(tick_names):
            value_offset = offset + 4 + tick_index * 2
            value = int.from_bytes(block[value_offset : value_offset + 2], "little")
            if value in (0, 0xFFFF):
                raise ValueError(
                    f"{OP_NAMES[op_id]} {size}-byte {name} is invalid: {value:#06x}"
                )
            ticks[name] = value

        checksum = int.from_bytes(block[offset + 12 : offset + 14], "little")
        declared_expected = int.from_bytes(
            block[offset + 14 : offset + 16], "little"
        )
        host_expected = expected[op_id][size_index]
        if checksum != host_expected or declared_expected != host_expected:
            raise ValueError(
                f"{OP_NAMES[op_id]} {size}-byte checksum pair is "
                f"{checksum:#06x}/{declared_expected:#06x}; expected "
                f"{host_expected:#06x}"
            )

        record = {
            "operation_id": op_id,
            "operation": OP_NAMES[op_id],
            "size": size,
            **ticks,
            "checksum": checksum,
        }
        record["8502_offload_delta_ticks"] = (
            record["offload_to_z80_ticks"] - record["local_8502_ticks"]
        )
        record["z80_offload_delta_ticks"] = (
            record["offload_to_8502_ticks"] - record["local_z80_ticks"]
        )
        records.append(record)

    crossovers = {}
    for op_id, name in OP_NAMES.items():
        operation_records = [
            record for record in records if record["operation_id"] == op_id
        ]
        crossovers[name] = {
            "8502_executive_offload_to_z80": _first_crossover(
                operation_records, "local_8502_ticks", "offload_to_z80_ticks"
            ),
            "z80_executive_offload_to_8502": _first_crossover(
                operation_records, "local_z80_ticks", "offload_to_8502_ticks"
            ),
        }

    return {
        "format": block[4],
        "8502_mhz": block[10],
        "z80_timing_requirement": "stock-2-tstates-per-system-tick-not-encoded",
        "timer": "cia1-timer-b",
        "source_address": 0xC000,
        "destination_address": 0xC800,
        "records": records,
        "crossovers": crossovers,
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
        raise SystemExit(f"invalid offload-benchmark result: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"8502 speed: {result['8502_mhz']} MHz")
    print(f"Z80 timing requirement: {result['z80_timing_requirement']}")
    print("operation     bytes  8502 local  -> Z80   Z80 local  -> 8502")
    for record in result["records"]:
        print(
            f"{record['operation']:<12} {record['size']:>5} "
            f"{record['local_8502_ticks']:>11} "
            f"{record['offload_to_z80_ticks']:>7} "
            f"{record['local_z80_ticks']:>11} "
            f"{record['offload_to_8502_ticks']:>8}"
        )
    print("Crossovers (first tested size where complete offload beats local):")
    for operation, directions in result["crossovers"].items():
        to_z80 = directions["8502_executive_offload_to_z80"]
        to_8502 = directions["z80_executive_offload_to_8502"]
        print(
            f"  {operation:<10} 8502->Z80: "
            f"{to_z80['size'] if to_z80 else 'none <= 2048'}; "
            f"Z80->8502: {to_8502['size'] if to_8502 else 'none <= 2048'}"
        )


if __name__ == "__main__":
    main()

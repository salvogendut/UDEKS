#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS service-registry status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF090
RESULT_SIZE = 24


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"registry record is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"SREG":
        raise ValueError("service-registry status magic is not SREG")
    if block[4] != 1:
        raise ValueError(f"unsupported service-registry status format {block[4]}")
    if block[5] != 2:
        if block[5] & 0x80:
            raise ValueError(f"service registry failed with code {block[6]:#04x}")
        raise ValueError(f"service-registry state is {block[5]}, not ready")
    if block[6] != 0 or block[9] != 0:
        raise ValueError("ready registry reports a failure")
    if block[7] == 0:
        raise ValueError("service registry discovered no descriptors")
    if block[8] != block[7] or block[17] != block[7]:
        raise ValueError(
            "service counts disagree: "
            f"table={block[17]}, discovered={block[7]}, started={block[8]}"
        )
    if block[12] != 0:
        raise ValueError(f"last service returned {block[12]:#04x}")
    if block[13:15] != b"\x00\x01":
        raise ValueError(
            f"unexpected service ABI {block[13]}.{block[14]}; expected 0.1"
        )
    if block[15] != 16:
        raise ValueError(f"descriptor size is {block[15]}; expected 16")
    return {
        "format": block[4],
        "state": block[5],
        "failure": block[6],
        "discovered": block[7],
        "started": block[8],
        "failed": block[9],
        "last_class": block[10],
        "last_instance": block[11],
        "last_result": block[12],
        "abi_major": block[13],
        "abi_minor": block[14],
        "descriptor_size": block[15],
        "last_flags": block[16],
        "table_count": block[17],
        "poll_passes": block[18] | (block[19] << 8),
        "poll_failed_index": block[20],
        "last_poll_result": block[21],
        "poll_failures": block[22],
        "polled_services": block[23],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="registry record, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid service-registry record: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        "Service registry: ready "
        f"({result['started']}/{result['table_count']} services, "
        f"ABI {result['abi_major']}.{result['abi_minor']})"
    )
    print(
        f"Polling: {result['poll_passes']} passes; "
        f"{result['polled_services']} vectors in latest pass"
    )


if __name__ == "__main__":
    main()

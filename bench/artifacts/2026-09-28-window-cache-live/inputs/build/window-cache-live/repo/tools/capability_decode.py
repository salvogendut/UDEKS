#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS hardware-capability record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF0C0
RESULT_SIZE = 32


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"capability record is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"HCAP":
        raise ValueError("hardware-capability magic is not HCAP")
    if block[4] != 1:
        raise ValueError(f"unsupported capability format {block[4]}")
    if block[5] != 2:
        if block[5] & 0x80:
            raise ValueError(f"capability probe failed with code {block[6]:#04x}")
        raise ValueError(f"capability state is {block[5]}, not ready")
    if block[6] != 0:
        raise ValueError(f"ready capability record has failure {block[6]:#04x}")
    if block[7] not in (1, 2):
        raise ValueError(f"unknown video standard {block[7]}")
    expected_family = 2 if block[8] >= 2 else 1
    if block[9] != expected_family:
        raise ValueError(
            f"VDC revision {block[8]} disagrees with family {block[9]}"
        )
    if block[10] not in (16, 64):
        raise ValueError(f"unsupported VDC RAM size {block[10]} KiB")
    if block[12] not in (0, 1) or block[13] not in (0, 1):
        raise ValueError("expansion presence fields are not boolean")
    if block[14] != expected_family:
        raise ValueError("machine-family hint disagrees with VDC family")
    if block[15] != 0x1F:
        raise ValueError(f"probe completion mask is {block[15]:#04x}, expected 0x1f")

    expected_flags = 0x01 if block[7] == 1 else 0x02
    if block[10] == 64:
        expected_flags |= 0x04
    if block[12]:
        expected_flags |= 0x08
    if block[13]:
        expected_flags |= 0x10
    if block[9] == 2:
        expected_flags |= 0x20
    if block[11] != expected_flags:
        raise ValueError(
            f"capability flags are {block[11]:#04x}; expected {expected_flags:#04x}"
        )
    if any(block[17:32]):
        raise ValueError("reserved capability bytes are nonzero")

    return {
        "format": block[4],
        "state": block[5],
        "video_standard": block[7],
        "vdc_revision": block[8],
        "vdc_family": block[9],
        "vdc_ram_kib": block[10],
        "flags": block[11],
        "reu_present": block[12],
        "georam_present": block[13],
        "machine_hint": block[14],
        "completion": block[15],
        "vdc_memory_config": block[16],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="capability record, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid hardware-capability record: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    standard = "PAL" if result["video_standard"] == 1 else "NTSC"
    family = "8568-family" if result["vdc_family"] == 2 else "8563-family"
    expansions = []
    if result["reu_present"]:
        expansions.append("REU")
    if result["georam_present"]:
        expansions.append("GeoRAM")
    print(
        f"Hardware: {standard}, {family} revision {result['vdc_revision']}, "
        f"{result['vdc_ram_kib']} KiB VDC RAM"
    )
    print("Expansions: " + (", ".join(expansions) if expansions else "none detected"))


if __name__ == "__main__":
    main()

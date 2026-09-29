#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate an UDEKS benchmark result block."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


RESULT_BASE = 0xF100
RESULT_SIZE = 128
HEADER_SIZE = 16
RECORD_SIZE = 8
VSF_MAGIC = b"VICE Snapshot File\x1a"

CPU_NAMES = {1: "8502", 2: "z80"}
CASE_NAMES = {
    1: "empty",
    2: "fill",
    3: "copy",
    4: "checksum",
    5: "control",
    6: "arith16",
}


def _source_bytes() -> list[int]:
    source = []
    value = 0x5A
    for index in range(256):
        value = ((value << 1) ^ (0x1D if value & 0x80 else 0) ^ index) & 0xFF
        source.append(value)
    return source


def expected_checksums() -> dict[int, int]:
    source = _source_bytes()
    block_sum = sum(source[:128]) & 0xFFFF

    state = 0xACE1
    for index in range(128):
        branch = state & 3
        if branch == 0:
            state = (state + index + 0x0101) & 0xFFFF
        elif branch == 1:
            state = (state ^ (index << 3)) & 0xFFFF
        elif branch == 2:
            state = ((state >> 1) | (state << 15)) & 0xFFFF
        else:
            state = (state - index - 0x001D) & 0xFFFF

    value = 0x1357
    for index in range(64):
        value = ((value << 1) + 0x1234) & 0xFFFF
        value = (value ^ (index | (index << 8))) & 0xFFFF

    return {
        1: 0xBEEF,
        2: (128 * 0x31) & 0xFFFF,
        3: block_sum,
        4: block_sum,
        5: state,
        6: value,
    }


def parse_result(data: bytes) -> dict[str, object]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"result block is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"BMRK":
        raise ValueError("benchmark magic is not BMRK")
    if block[4] != 1:
        raise ValueError(f"unsupported benchmark format {block[4]}")
    if block[5] not in CPU_NAMES:
        raise ValueError(f"unknown CPU identifier {block[5]}")
    if block[8] != 2:
        raise ValueError(f"benchmark state is {block[8]}, not complete")
    if block[9] != RECORD_SIZE:
        raise ValueError(f"record size is {block[9]}, expected {RECORD_SIZE}")

    count = block[7]
    if count > (RESULT_SIZE - HEADER_SIZE) // RECORD_SIZE:
        raise ValueError(f"record count {count} exceeds the result block")

    expected = expected_checksums()
    records = []
    seen = set()
    for index in range(count):
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
        if status != 0:
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
        "cpu": CPU_NAMES[block[5]],
        "configuration": block[6],
        "timer": "cia1-timer-b" if block[10] == 1 else f"unknown-{block[10]}",
        "records": records,
    }


def extract_memory(
    image: bytes, address: int, size: int, offset: int | None = None
) -> bytes:
    if image.startswith(VSF_MAGIC):
        if offset is not None:
            raise ValueError("--offset does not apply to a VSF snapshot")
        position = 58
        while position + 22 <= len(image):
            name = image[position : position + 16].split(b"\0", 1)[0]
            module_size = int.from_bytes(image[position + 18 : position + 22], "little")
            if module_size < 22 or position + module_size > len(image):
                raise ValueError("invalid VSF module size")
            if name == b"1986STATE":
                payload = position + 22
                if image[payload : payload + 4] != b"1986":
                    raise ValueError("invalid 1986STATE magic")
                z80_size = int.from_bytes(image[payload + 8 : payload + 12], "little")
                mmu_size = int.from_bytes(image[payload + 12 : payload + 16], "little")
                ram = payload + 36 + 32 + z80_size + mmu_size
                end = ram + address + size
                if end > position + module_size:
                    raise ValueError("truncated 1986STATE RAM")
                return image[ram + address : end]
            position += module_size
        raise ValueError("VSF has no 1986STATE module")

    if offset is None:
        offset = address if len(image) >= address + size else 0
    if offset < 0 or offset + size > len(image):
        raise ValueError(
            f"result range {offset:#x}..{offset + size - 1:#x} "
            f"is outside the input ({len(image)} bytes)"
        )
    return image[offset : offset + size]


def extract_result(image: bytes, offset: int | None = None) -> bytes:
    return extract_memory(image, RESULT_BASE, RESULT_SIZE, offset)


def format_text(result: dict[str, object]) -> str:
    lines = [
        f"CPU: {result['cpu']}",
        f"Configuration: {result['configuration']}",
        f"Timer: {result['timer']}",
        "case          iterations    ticks  checksum",
    ]
    for record in result["records"]:
        lines.append(
            f"{record['name']:<13} {record['iterations']:>10} "
            f"{record['ticks']:>8}  0x{record['checksum']:04x}"
        )
    return "\n".join(lines)


def parse_number(value: str) -> int:
    return int(value, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="128-byte block or memory dump")
    parser.add_argument(
        "--offset",
        type=parse_number,
        help="block offset; inferred as 0xf100 for a 64 KiB dump, otherwise 0",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    try:
        block = extract_result(args.input.read_bytes(), args.offset)
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid benchmark result: {error}") from error
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()

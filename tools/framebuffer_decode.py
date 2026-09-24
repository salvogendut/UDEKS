#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS VDC framebuffer status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF0E0
RESULT_SIZE = 32


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(
            f"framebuffer record is {len(data)} bytes; expected {RESULT_SIZE}"
        )
    block = data[:RESULT_SIZE]
    if block[:4] != b"VFBR":
        raise ValueError("framebuffer status magic is not VFBR")
    if block[4] not in (1, 2, 3):
        raise ValueError(f"unsupported framebuffer status format {block[4]}")
    if block[5] != 2:
        if block[5] & 0x80:
            raise ValueError(f"framebuffer service failed with code {block[6]:#04x}")
        raise ValueError(f"framebuffer state is {block[5]}, not ready")
    expected = {
        6: 0,
        7: 80,
        8: 200,
        9: 1,
        24: 0x0D,
    }
    if block[4] < 3:
        expected.update(
            {
                15: 20,
                16: 160,
                17: 30,
                18: 20,
                19: 0x5E,
                20: 0x06,
                21: 0x2E,
                22: 0x28,
            }
        )
    else:
        expected.update(
            {
                15: 8,
                16: 64,
                17: 70,
                18: 12,
                19: 0x06,
                20: 0x04,
                21: 0x73,
                22: 0x58,
            }
        )
    expected[23] = 0x1F if block[4] == 1 else 0x7F
    if block[4] >= 2:
        expected.update({25: 5, 26: 7, 27: 9, 30: 0x1F})
    for offset, value in expected.items():
        if block[offset] != value:
            raise ValueError(
                f"framebuffer field {offset} is {block[offset]:#04x}; "
                f"expected {value:#04x}"
            )
    if block[10] not in (16, 64):
        raise ValueError(f"unsupported VDC RAM size {block[10]} KiB")
    expected_mode = 0x80 | (block[11] & 0x0F)
    if block[12] != expected_mode:
        raise ValueError(
            f"bitmap mode is {block[12]:#04x}; expected {expected_mode:#04x}"
        )
    if block[4] == 1:
        if any(block[25:32]):
            raise ValueError("reserved framebuffer bytes are nonzero")
    else:
        if block[28] == 0 and block[29] == 0:
            raise ValueError("font render checksum is zero")
        if block[31] != 0:
            raise ValueError("reserved framebuffer byte is nonzero")
    return {
        "format": block[4],
        "state": block[5],
        "failure": block[6],
        "stride": block[7],
        "height": block[8],
        "vdc_ram_kib": block[10],
        "saved_mode": block[11],
        "bitmap_mode": block[12],
        "splash_address": block[19] | (block[20] << 8),
        "splash_checksum": block[21] | (block[22] << 8),
        "flags": block[23],
        "color": block[24],
        "font_width": block[25] if block[4] >= 2 else 0,
        "font_height": block[26] if block[4] >= 2 else 0,
        "font_checksum": (
            block[28] | (block[29] << 8) if block[4] >= 2 else 0
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="framebuffer record, dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid framebuffer record: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        f"VDC framebuffer: ready (640x{result['height']}, "
        f"{result['vdc_ram_kib']} KiB VDC)"
    )
    print(
        f"Splash verified at ${result['splash_address']:04X}; "
        f"checksum ${result['splash_checksum']:04X}"
    )
    if result["format"] >= 2:
        print(
            f"Software font: {result['font_width']}x{result['font_height']}, "
            f"hardware panel checksum ${result['font_checksum']:04X}"
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the UDEKS VDC console-service status record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF070
RESULT_SIZE = 24


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"console record is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"VCON":
        raise ValueError("console status magic is not VCON")
    if block[4] not in (1, 2):
        raise ValueError(f"unsupported console status format {block[4]}")
    if block[5] != 2:
        if block[5] & 0x80:
            raise ValueError(f"console service failed with code {block[6]:#04x}")
        raise ValueError(f"console state is {block[5]}, not ready")
    expected = {
        6: 0x00,
        7: 80,
        8: 25,
        10: 0x00,
        11: 0x08,
        12: 0x15,
    }
    if block[4] == 1:
        expected.update({9: 0x0F, 13: 0x0F, 16: 0xF0})
    else:
        expected.update({9: 0x00, 13: 0x00, 16: 0x0D})
    for offset, value in expected.items():
        if block[offset] != value:
            raise ValueError(
                f"console field {offset} is {block[offset]:#04x}; expected {value:#04x}"
            )
    if not block[15] & 0x40:
        raise ValueError("VDC attributes are not enabled")
    if block[19] & ~0x07:
        raise ValueError("VDC running-app mask has unknown bits")
    return {
        "format": block[4],
        "state": block[5],
        "failure": block[6],
        "width": block[7],
        "height": block[8],
        "attribute": block[9],
        "screen_readback": block[12],
        "attribute_readback": block[13],
        "horizontal_scroll": block[15],
        "color": block[16],
        "app_mask": block[19],
        "app_panel_updates": block[20] | (block[21] << 8),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="console record, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid VDC console record: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        f"VDC console: ready ({result['width']}x{result['height']}); "
        f"running-app mask 0x{result['app_mask']:02x}"
    )
    print(
        "Readback: screen 0x"
        f"{result['screen_readback']:02x}, attribute 0x{result['attribute_readback']:02x}"
    )


if __name__ == "__main__":
    main()

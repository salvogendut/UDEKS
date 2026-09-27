#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Wrap the linked scheduler tail in its deterministic boot-load envelope."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

LOAD_ADDRESS = 0x5000
TAIL_ADDRESS = 0xC120
TAIL_LIMIT = 0xCF00
MAGIC = b"USOV"
ABI_MAJOR = 0
ABI_MINOR = 1
HEADER_SIZE = 16

SEGMENT = re.compile(
    r"^([A-Z][A-Z0-9]*)\s+([0-9A-Fa-f]{6})\s+"
    r"([0-9A-Fa-f]{6})\s+([0-9A-Fa-f]{6})\s+",
    re.MULTILINE,
)


def map_segments(text: str) -> dict[str, tuple[int, int, int]]:
    return {
        name: (int(start, 16), int(end, 16), int(size, 16))
        for name, start, end, size in SEGMENT.findall(text)
    }


def build_overlay(image: bytes, map_text: str) -> bytes:
    segments = map_segments(map_text)
    if "CODE" not in segments or "BSS" not in segments:
        raise ValueError("scheduler overlay map lacks CODE or BSS")
    code_start = segments["CODE"][0]
    bss_start, bss_end, bss_size = segments["BSS"]
    if code_start != TAIL_ADDRESS:
        raise ValueError(f"scheduler tail starts at ${code_start:04X}, expected $C120")
    if len(image) != bss_start - code_start:
        raise ValueError(
            f"scheduler tail image is {len(image)} bytes; map requires "
            f"{bss_start - code_start}"
        )
    if bss_size == 0 or bss_end + 1 > TAIL_LIMIT:
        raise ValueError("scheduler BSS is empty or exceeds $CEFF")
    checksum = sum(image) & 0xFFFF
    header = bytearray(MAGIC)
    header += bytes((ABI_MAJOR, ABI_MINOR))
    header += code_start.to_bytes(2, "little")
    header += len(image).to_bytes(2, "little")
    header += bss_start.to_bytes(2, "little")
    header += bss_size.to_bytes(2, "little")
    header += checksum.to_bytes(2, "little")
    if len(header) != HEADER_SIZE:
        raise AssertionError("scheduler overlay header size drifted")
    return LOAD_ADDRESS.to_bytes(2, "little") + header + image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("map", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        payload = build_overlay(
            args.image.read_bytes(), args.map.read_text(encoding="utf-8")
        )
    except ValueError as error:
        raise SystemExit(f"cannot build scheduler overlay: {error}") from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert an Intel HEX image to a deterministic, bounded raw binary."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_number(value: str) -> int:
    return int(value, 0)


def read_ihx(path: Path) -> dict[int, int]:
    image: dict[int, int] = {}
    upper = 0
    saw_eof = False

    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        if not line.startswith(":"):
            raise ValueError(f"{path}:{line_number}: missing ':'")

        record = bytes.fromhex(line[1:])
        if len(record) < 5 or len(record) != record[0] + 5:
            raise ValueError(f"{path}:{line_number}: invalid record length")
        if sum(record) & 0xFF:
            raise ValueError(f"{path}:{line_number}: checksum mismatch")

        count = record[0]
        address = (record[1] << 8) | record[2]
        kind = record[3]
        payload = record[4 : 4 + count]

        if kind == 0x00:
            absolute = upper + address
            for index, byte in enumerate(payload):
                image[absolute + index] = byte
        elif kind == 0x01:
            saw_eof = True
            break
        elif kind == 0x02:
            if count != 2:
                raise ValueError(f"{path}:{line_number}: invalid segment record")
            upper = int.from_bytes(payload, "big") << 4
        elif kind == 0x04:
            if count != 2:
                raise ValueError(f"{path}:{line_number}: invalid linear record")
            upper = int.from_bytes(payload, "big") << 16
        elif kind not in (0x03, 0x05):
            raise ValueError(f"{path}:{line_number}: unsupported record {kind:#x}")

    if not saw_eof:
        raise ValueError(f"{path}: missing EOF record")
    return image


def convert(source: Path, destination: Path, start: int, end: int) -> None:
    if start < 0 or end <= start:
        raise ValueError("invalid output address range")

    image = read_ihx(source)
    outside = sorted(address for address in image if not start <= address < end)
    if outside:
        raise ValueError(
            f"image contains data outside {start:#x}..{end - 1:#x}: "
            f"first address is {outside[0]:#x}"
        )

    output = bytearray([0] * (end - start))
    for address, byte in image.items():
        output[address - start] = byte
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, type=parse_number)
    parser.add_argument("--end", required=True, type=parse_number)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    convert(args.source, args.destination, args.start, args.end)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Wrap a raw 6502-family image in a Commodore PRG load header."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_number(value: str) -> int:
    return int(value, 0)


def convert(source: Path, destination: Path, load_address: int) -> None:
    if not 0 <= load_address <= 0xFFFF:
        raise ValueError("load address must fit in 16 bits")
    payload = source.read_bytes()
    if load_address + len(payload) > 0x10000:
        raise ValueError("image extends beyond the 16-bit address space")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(load_address.to_bytes(2, "little") + payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load-address", required=True, type=parse_number)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    convert(args.source, args.destination, args.load_address)


if __name__ == "__main__":
    main()

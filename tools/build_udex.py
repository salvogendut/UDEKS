#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Wrap a flat target image in the fixed-address UDEKS executable format."""

from __future__ import annotations

import argparse
from pathlib import Path


MAGIC = b"UDEX"
ABI_MAJOR = 0
ABI_MINOR = 1
HEADER_SIZE = 16
CPU_IDS = {"8502": 1, "z80": 2}
FLAG_PERSISTENT_POLL = 0x01
SUPPORTED_FLAGS = FLAG_PERSISTENT_POLL


def parse_number(text: str) -> int:
    return int(text, 0)


def build_executable(
    image: bytes,
    *,
    cpu: int,
    load_address: int,
    entry_address: int,
    bss_size: int = 0,
    flags: int = 0,
) -> bytes:
    if cpu not in CPU_IDS.values():
        raise ValueError("unsupported executable CPU")
    if flags & ~SUPPORTED_FLAGS:
        raise ValueError("format 0.1 executable has unsupported flags")
    if not image or len(image) > 0xFFFF:
        raise ValueError("executable image size must be 1..65535 bytes")
    if not 0 <= load_address <= 0xFFFF:
        raise ValueError("load address must fit in 16 bits")
    if not 0 <= bss_size <= 0xFFFF:
        raise ValueError("BSS size must fit in 16 bits")
    image_limit = load_address + len(image)
    allocation_limit = image_limit + bss_size
    if image_limit > 0x10000 or allocation_limit > 0x10000:
        raise ValueError("executable image and BSS must fit in target memory")
    if not load_address <= entry_address < image_limit:
        raise ValueError("entry address must lie inside the executable image")

    header = bytearray(HEADER_SIZE)
    header[:4] = MAGIC
    header[4:8] = bytes((ABI_MAJOR, ABI_MINOR, cpu, flags))
    header[8:10] = load_address.to_bytes(2, "little")
    header[10:12] = len(image).to_bytes(2, "little")
    header[12:14] = bss_size.to_bytes(2, "little")
    header[14:16] = entry_address.to_bytes(2, "little")
    return bytes(header) + image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="flat linked target image")
    parser.add_argument("output", type=Path, help="UDEX output path")
    parser.add_argument("--cpu", choices=CPU_IDS, required=True)
    parser.add_argument("--load-address", type=parse_number, required=True)
    parser.add_argument("--entry-address", type=parse_number)
    parser.add_argument("--bss-size", type=parse_number, default=0)
    parser.add_argument("--flags", type=parse_number, default=0)
    args = parser.parse_args()

    entry_address = (
        args.load_address
        if args.entry_address is None
        else args.entry_address
    )
    try:
        output = build_executable(
            args.input.read_bytes(),
            cpu=CPU_IDS[args.cpu],
            load_address=args.load_address,
            entry_address=entry_address,
            bss_size=args.bss_size,
            flags=args.flags,
        )
    except ValueError as error:
        raise SystemExit(f"cannot build UDEX image: {error}") from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the deterministic UDEKS read-only boot filesystem."""

from __future__ import annotations

import argparse
from pathlib import Path


MAGIC = b"UBFS"
ABI_MAJOR = 0
ABI_MINOR = 1
HEADER_SIZE = 16
ENTRY_SIZE = 24
NAME_SIZE = 16
ENTRY_EXECUTABLE = 0x01
DEFAULT_MAX_SIZE = 0x0800
ALLOWED_NAME_BYTES = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._+-"
)


def validate_name(name: str) -> bytes:
    try:
        encoded = name.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("bootfs names must be ASCII") from error
    if not 1 <= len(encoded) <= NAME_SIZE:
        raise ValueError(f"bootfs names must be 1..{NAME_SIZE} bytes")
    if any(value not in ALLOWED_NAME_BYTES for value in encoded):
        raise ValueError("bootfs name contains an unsupported character")
    return encoded


def build_bootfs(entries: list[tuple[str, bytes]], max_size: int = DEFAULT_MAX_SIZE) -> bytes:
    if not entries:
        raise ValueError("bootfs requires at least one entry")
    if len(entries) > 255:
        raise ValueError("bootfs has too many entries")
    normalized = [(validate_name(name), bytes(data)) for name, data in entries]
    normalized.sort(key=lambda item: item[0])
    for index, (name, data) in enumerate(normalized):
        if index != 0 and normalized[index - 1][0] == name:
            raise ValueError(f"duplicate bootfs name: {name.decode('ascii')}")
        if not data:
            raise ValueError(f"bootfs entry {name.decode('ascii')} is empty")

    data_offset = HEADER_SIZE + len(normalized) * ENTRY_SIZE
    total_size = data_offset + sum(len(data) for _, data in normalized)
    if total_size > max_size or total_size > 0xFFFF:
        raise ValueError("bootfs image exceeds its configured size")

    image = bytearray(total_size)
    image[0:4] = MAGIC
    image[4:8] = bytes((ABI_MAJOR, ABI_MINOR, len(normalized), ENTRY_SIZE))
    image[8:10] = HEADER_SIZE.to_bytes(2, "little")
    image[10:12] = data_offset.to_bytes(2, "little")
    image[12:14] = total_size.to_bytes(2, "little")

    cursor = data_offset
    for index, (name, data) in enumerate(normalized):
        entry = HEADER_SIZE + index * ENTRY_SIZE
        image[entry] = ENTRY_EXECUTABLE
        image[entry + 1] = len(name)
        image[entry + 2 : entry + 4] = cursor.to_bytes(2, "little")
        image[entry + 4 : entry + 6] = len(data).to_bytes(2, "little")
        image[entry + 8 : entry + 8 + len(name)] = name
        image[cursor : cursor + len(data)] = data
        cursor += len(data)
    return bytes(image)


def parse_entry(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or not path:
        raise argparse.ArgumentTypeError("entry must use NAME=FILE")
    return name, Path(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entry", action="append", type=parse_entry, required=True,
        metavar="NAME=FILE",
    )
    parser.add_argument("--max-size", type=lambda value: int(value, 0), default=DEFAULT_MAX_SIZE)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        image = build_bootfs(
            [(name, path.read_bytes()) for name, path in args.entry],
            args.max_size,
        )
    except (OSError, ValueError) as error:
        raise SystemExit(f"cannot build bootfs: {error}") from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)


if __name__ == "__main__":
    main()

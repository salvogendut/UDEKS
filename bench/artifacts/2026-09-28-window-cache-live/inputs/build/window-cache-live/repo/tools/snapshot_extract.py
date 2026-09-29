#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Extract an address range from a 1986 VSF or a flat memory image."""

from __future__ import annotations

import argparse
from pathlib import Path

from bench_decode import extract_memory, parse_number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="1986 VSF or flat memory image")
    parser.add_argument("output", type=Path, help="raw output file")
    parser.add_argument("--address", type=parse_number, required=True)
    parser.add_argument("--size", type=parse_number, required=True)
    parser.add_argument(
        "--offset",
        type=parse_number,
        help="input offset for a flat image; invalid for a VSF",
    )
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), args.address, args.size, args.offset
        )
    except ValueError as error:
        raise SystemExit(f"cannot extract snapshot memory: {error}") from error

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(block)
    print(
        f"extracted {len(block)} bytes from ${args.address:04X} to {args.output}"
    )


if __name__ == "__main__":
    main()

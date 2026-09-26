#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Join the staged crt0 page and resident kernel into a direct-load image.

The development PRG loads at $1C00: crt0 fills $1C00-$1CFF, the gap to $2000
is zero-filled, and the resident kernel follows at $2000.  Enter the result
with SYS 7168.
"""

from __future__ import annotations

import argparse
from pathlib import Path


CRT0_ADDRESS = 0x1C00
CRT0_SIZE = 0x0100
KERNEL_ADDRESS = 0x2000


def join(crt0: bytes, kernel: bytes, destination: Path) -> None:
    if len(crt0) > CRT0_SIZE:
        raise ValueError(f"crt0 exceeds its {CRT0_SIZE}-byte page")
    if not kernel:
        raise ValueError("resident kernel image is empty")
    image = bytearray(crt0.ljust(CRT0_SIZE, b"\x00"))
    image.extend(bytes(KERNEL_ADDRESS - (CRT0_ADDRESS + CRT0_SIZE)))
    image.extend(kernel)
    if CRT0_ADDRESS + len(image) > 0x10000:
        raise ValueError("direct image extends beyond the 16-bit address space")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(image)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("crt0", type=Path)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        join(args.crt0.read_bytes(), args.kernel.read_bytes(), args.destination)
    except (OSError, ValueError) as error:
        raise SystemExit(f"cannot join direct boot image: {error}") from error


if __name__ == "__main__":
    main()

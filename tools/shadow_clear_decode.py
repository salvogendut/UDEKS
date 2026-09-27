#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode the preserved shadow-clear boot probe blocks.

`shadow-preimage.bin` is the staged `$ABFE-$CEFF` image: the 8,000-byte
VICSHADOW segment (seeded nonzero across the newly reclaimed `$ABFE-$ADFF`
prefix, with the live `$AE00-$AEFF` crt0 staging) followed by the reclaimed
tail.  `shadow-after-boot.bin` is the same
window after crt0: the shadow must be entirely zero and every tail byte must
still match the preimage.  `shadow-drawn.bin` and `vic-bitmap.bin` are both
8,000 bytes and must match after a client repaint.
"""

from __future__ import annotations

import argparse
from pathlib import Path


SHADOW_SIZE = 8000
SYSCALL_PAGE = 0xCF00


def parse_window(
    block: bytes,
    preimage: bytes,
    shadow_start: int,
    shadow_size: int,
) -> dict[str, object]:
    if len(block) < shadow_size:
        raise ValueError("shadow window is truncated")
    if len(preimage) != len(block):
        raise ValueError("preimage length does not match the window")
    if shadow_start + len(block) > SYSCALL_PAGE:
        raise ValueError("shadow window crosses the fixed SYSCALLS page")
    shadow = block[:shadow_size]
    nonzero = sum(1 for byte in shadow if byte != 0)
    mismatches = [
        offset - shadow_size
        for offset in range(shadow_size, len(block))
        if block[offset] != preimage[offset]
    ]
    return {
        "shadow_start": shadow_start,
        "shadow_size": shadow_size,
        "shadow_nonzero": nonzero,
        "shadow_cleared": nonzero == 0,
        "tail_size": len(block) - shadow_size,
        "tail_mismatches": mismatches,
        "tail_intact": not mismatches,
    }


def compare_shadow_bitmap(shadow: bytes, bitmap: bytes) -> list[int]:
    if len(shadow) != len(bitmap):
        raise ValueError("shadow and bitmap sizes differ")
    return [
        offset
        for offset, (left, right) in enumerate(zip(shadow, bitmap))
        if left != right
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", type=Path,
        help="directory holding shadow-after-boot.bin, shadow-preimage.bin, "
             "shadow-drawn.bin, and vic-bitmap.bin",
    )
    parser.add_argument("--shadow-start", type=lambda v: int(v, 0),
                        default=0xABFE)
    args = parser.parse_args()
    window = (args.root / "shadow-after-boot.bin").read_bytes()
    preimage = (args.root / "shadow-preimage.bin").read_bytes()
    result = parse_window(window, preimage, args.shadow_start, SHADOW_SIZE)
    print(
        f"shadow ${args.shadow_start:04X}: "
        f"{result['shadow_nonzero']} nonzero bytes; "
        f"tail mismatches: {len(result['tail_mismatches'])}"
    )
    shadow = (args.root / "shadow-drawn.bin").read_bytes()
    bitmap = (args.root / "vic-bitmap.bin").read_bytes()
    mismatches = compare_shadow_bitmap(shadow, bitmap)
    print(f"drawn shadow vs bank-1 bitmap: {len(mismatches)} mismatched bytes")
    if (
        not result["shadow_cleared"]
        or not result["tail_intact"]
        or mismatches
    ):
        raise SystemExit("shadow clear qualification failed")
    print("shadow clear qualification OK")


if __name__ == "__main__":
    main()

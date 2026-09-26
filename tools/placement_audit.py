#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit the resident 8502 linker map for the scheduler placement budget."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from bench_decode import parse_number


ROOT = Path(__file__).resolve().parents[1]

KERNEL_BASE = 0x2000
SYSCALL_PAGE = 0xCF00
VIC_SHADOW_SEGMENT = "VICSHADOW"
VIC_SHADOW_START = 0xAF00
BOOT_GATEWAY_BASE = 0xF700
BOOT_GATEWAY_LIMIT = 0xF7F0
VIC_GATEWAY_BASE = 0xF68A
VIC_GATEWAY_LARGEST = 254

# Objects whose code runs only during boot or hardware discovery and is dead
# afterwards. Relocating them is the first reclaim step.
BOOT_ONLY_OBJECTS = (
    "boot_console.o",
    "probe.o",
    "hardware_capability.o",
    "crt0.o",
)

CODE_SEGMENTS = (
    "STARTUP", "LOWCODE", "ONCE", "CODE", "RODATA", "DATA",
    "MODULECODE", "MODULERODATA", "BOOTFSCODE", "SYSCALLS",
    "TASKREQUEST", "TASKGATE",
)


def parse_map(text: str) -> tuple[dict[str, int], list[tuple[str, int, int, int]]]:
    modules: dict[str, int] = {}
    segments: list[tuple[str, int, int, int]] = []

    current = None
    in_modules = True
    for line in text.splitlines():
        if line.startswith("Segment list:"):
            in_modules = False
            continue
        if in_modules:
            match = re.match(r"^(\S+):$", line)
            if match:
                current = match.group(1)
                modules.setdefault(current, 0)
                continue
            match = re.match(
                r"^\s+(\S+)\s+Offs=[0-9A-Fa-f]+\s+Size=([0-9A-Fa-f]+)", line
            )
            if match and current is not None:
                modules[current] += int(match.group(2), 16)
            continue
        match = re.match(
            r"^(\S+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)", line
        )
        if match:
            segments.append(
                (
                    match.group(1),
                    int(match.group(2), 16),
                    int(match.group(3), 16),
                    int(match.group(4), 16),
                )
            )
    return modules, segments


def vic_bitmap_size() -> int:
    header = (ROOT / "include/udeks/vic_graphics.h").read_text(encoding="utf-8")
    match = re.search(
        r"^#define\s+UDEKS_VIC_BITMAP_SIZE\s+(\d+)u?$", header, re.MULTILINE
    )
    if match is None:
        raise ValueError("UDEKS_VIC_BITMAP_SIZE is missing")
    return int(match.group(1))


def audit(map_text: str) -> dict[str, object]:
    modules, segments = parse_map(map_text)
    by_name = {name: (start, end, size) for name, start, end, size in segments}

    data_segments = [
        (start, end) for name, start, end, _ in segments
        if name in ("STARTUP", "LOWCODE", "ONCE", "CODE", "RODATA", "DATA", "BSS")
    ]
    data_end = max(end for _, end in data_segments)

    shadow = by_name.get(VIC_SHADOW_SEGMENT)
    if shadow is None:
        raise ValueError("VICSHADOW segment is missing")
    shadow_start = shadow[0]
    shadow_size = shadow[2]
    padding = shadow_size - vic_bitmap_size()
    kernel_gap = shadow_start - data_end

    boot_only = {
        name: modules.get(name, 0)
        for name in BOOT_ONLY_OBJECTS
    }
    reclaim_total = sum(boot_only.values()) + kernel_gap + padding

    return {
        "kernel_base": KERNEL_BASE,
        "syscall_page": SYSCALL_PAGE,
        "data_end": data_end,
        "kernel_gap": kernel_gap,
        "vic_shadow_start": shadow_start,
        "vic_shadow_size": shadow_size,
        "vic_shadow_padding": padding,
        "boot_only": boot_only,
        "boot_only_total": sum(boot_only.values()),
        "reclaim_total": reclaim_total,
        "boot_gateway_bytes": BOOT_GATEWAY_LIMIT - BOOT_GATEWAY_BASE,
        "vic_gateway_uncontested_bytes": (
            BOOT_GATEWAY_LIMIT - (VIC_GATEWAY_BASE + VIC_GATEWAY_LARGEST)
        ),
        "largest_objects": sorted(
            (
                {"name": name, "bytes": size}
                for name, size in modules.items()
            ),
            key=lambda row: row["bytes"],
            reverse=True,
        )[:10],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "map", type=Path,
        nargs="?",
        default=ROOT / "build/8502/udeks-8502.map",
        help="ld65 map file (default: build/8502/udeks-8502.map)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        result = audit(args.map.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"placement audit failed: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        f"Bank-0 data ends at ${result['data_end']:04X}; "
        f"VIC shadow starts at ${result['vic_shadow_start']:04X}; "
        f"gap {result['kernel_gap']} bytes"
    )
    print(
        f"VIC shadow padding {result['vic_shadow_padding']} bytes; "
        f"boot-only objects {result['boot_only_total']} bytes"
    )
    for name, size in result["boot_only"].items():
        print(f"  {name:24s} {size:5d}")
    print(f"Total reclaimable: {result['reclaim_total']} bytes")
    print(
        f"Boot gateway page: {result['boot_gateway_bytes']} bytes; "
        f"uncontested after the VIC gateway: "
        f"{result['vic_gateway_uncontested_bytes']} bytes"
    )


if __name__ == "__main__":
    main()

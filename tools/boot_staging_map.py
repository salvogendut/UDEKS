#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Byte-accurate bank-0 staging/lifetime map for the boot-only objects.

The map is derived from the linker map, the payload staging constants in
tools/build_d71.py, and the boot-sector/stage-0 image.  It reports where the
staged boot-only images live, the free payload holes that could hold another
staged image, and whether the remaining boot-only objects fit.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from build_d71 import (
    BOOTFS_REQUEST_STAGING_ADDRESS,
    BOOTFS_REQUEST_STAGING_SIZE,
    BOOTFS_TAIL_STAGING_ADDRESS,
    BOOTFS_TAIL_SIZE,
    CRT0_SIZE,
    CRT0_STAGING_ADDRESS,
    MODULE_STAGING_ADDRESS,
    MODULE_STAGING_SIZE,
    PROBE_SIZE,
    PROBE_STAGING_ADDRESS,
    TASK_BANK_GATE_STAGING_ADDRESS,
    TASK_BANK_GATE_STAGING_SIZE,
    TASK_LOADER_STAGING_ADDRESS,
    TASK_LOADER_STAGING_SIZE,
    TASK_REQUEST_STAGING_ADDRESS,
    TASK_REQUEST_STAGING_SIZE,
)
from placement_audit import (
    SYSCALL_PAGE,
    VIC_SHADOW_SEGMENT,
    module_bss_size,
    module_code_size,
    parse_map,
)


ROOT = Path(__file__).resolve().parents[1]
BOOT_SECTOR_BASE = 0x0B00
BOOT_SECTOR_SIZE = 0x0100
BOOT_ONLY_OBJECTS = ("hardware_capability.o", "boot_console.o")


@dataclass(frozen=True)
class Region:
    name: str
    start: int
    end: int
    live: str


def staged_regions() -> list[Region]:
    return [
        Region(
            "probe staging",
            PROBE_STAGING_ADDRESS,
            PROBE_STAGING_ADDRESS + PROBE_SIZE - 1,
            "load..crt0",
        ),
        Region(
            "crt0 staging",
            CRT0_STAGING_ADDRESS,
            CRT0_STAGING_ADDRESS + CRT0_SIZE - 1,
            "load..crt0",
        ),
        Region(
            "bootfs tail staging",
            BOOTFS_TAIL_STAGING_ADDRESS,
            # build_d71 rejects a bootfs tail that reaches the module staging,
            # so the enforced boundary is the module base, not the padded
            # reservation end.
            min(
                BOOTFS_TAIL_STAGING_ADDRESS + BOOTFS_TAIL_SIZE,
                MODULE_STAGING_ADDRESS,
            )
            - 1,
            "load..stage1",
        ),
        Region(
            "module staging",
            MODULE_STAGING_ADDRESS,
            MODULE_STAGING_ADDRESS + MODULE_STAGING_SIZE - 1,
            "load..stage1",
        ),
        Region(
            "task request staging",
            TASK_REQUEST_STAGING_ADDRESS,
            TASK_REQUEST_STAGING_ADDRESS + TASK_REQUEST_STAGING_SIZE - 1,
            "load..stage1",
        ),
        Region(
            "bootfs request staging",
            BOOTFS_REQUEST_STAGING_ADDRESS,
            BOOTFS_REQUEST_STAGING_ADDRESS + BOOTFS_REQUEST_STAGING_SIZE - 1,
            "load..stage1",
        ),
        Region(
            "task loader staging",
            TASK_LOADER_STAGING_ADDRESS,
            TASK_LOADER_STAGING_ADDRESS + TASK_LOADER_STAGING_SIZE - 1,
            "load..stage1",
        ),
        Region(
            "task gate staging",
            TASK_BANK_GATE_STAGING_ADDRESS,
            TASK_BANK_GATE_STAGING_ADDRESS + TASK_BANK_GATE_STAGING_SIZE - 1,
            "load..stage1",
        ),
    ]


def shadow_bounds(map_text: str) -> tuple[int, int]:
    _, segments = parse_map(map_text)
    for name, start, end in segments:
        if name == VIC_SHADOW_SEGMENT:
            return start, end
    raise ValueError(f"{VIC_SHADOW_SEGMENT} segment is missing from the map")


def stage0_end(stage0: bytes) -> int:
    last = max(
        (offset for offset, byte in enumerate(stage0) if byte),
        default=0,
    )
    return BOOT_SECTOR_BASE + last


def free_holes(
    shadow_start: int, stage0_last: int
) -> list[tuple[str, int, int]]:
    """Payload byte ranges that can hold another staged boot-only image."""
    holes: list[tuple[str, int, int]] = []
    window_end = SYSCALL_PAGE - 1
    cursor = shadow_start
    for region in sorted(staged_regions(), key=lambda item: item.start):
        if region.end < shadow_start or region.start > window_end:
            continue
        if region.start > cursor:
            holes.append(("staging hole", cursor, region.start - 1))
        cursor = max(cursor, region.end + 1)
    if cursor <= window_end:
        holes.append(("staging hole", cursor, window_end))
    if stage0_last < BOOT_SECTOR_BASE + BOOT_SECTOR_SIZE - 1:
        holes.append(
            (
                "boot-sector hole",
                stage0_last + 1,
                BOOT_SECTOR_BASE + BOOT_SECTOR_SIZE - 1,
            )
        )
    return holes


def object_sizes(map_text: str) -> dict[str, int]:
    modules, _ = parse_map(map_text)
    sizes: dict[str, int] = {}
    for name in BOOT_ONLY_OBJECTS:
        segments = modules.get(name, {})
        sizes[name] = module_code_size(segments) + module_bss_size(segments)
    return sizes


def analyze(map_text: str, stage0: bytes) -> dict[str, object]:
    shadow_start, shadow_end = shadow_bounds(map_text)
    holes = free_holes(shadow_start, stage0_end(stage0))
    sizes = object_sizes(map_text)
    largest = max((end - start + 1 for _, start, end in holes), default=0)
    total = sum(end - start + 1 for _, start, end in holes)
    fits = {
        name: {
            "single_hole": size <= largest,
            "aggregate": size <= total,
        }
        for name, size in sizes.items()
    }
    return {
        "shadow_start": shadow_start,
        "shadow_end": shadow_end,
        "holes": holes,
        "hole_total": total,
        "largest_hole": largest,
        "objects": sizes,
        "fits": fits,
        "syscall_page": SYSCALL_PAGE,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--map", type=Path, default=ROOT / "build/8502/udeks-8502.map"
    )
    parser.add_argument(
        "--stage0", type=Path, default=ROOT / "build/boot/stage0.bin"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        result = analyze(
            args.map.read_text(encoding="utf-8"), args.stage0.read_bytes()
        )
    except (OSError, ValueError) as error:
        raise SystemExit(f"boot staging map failed: {error}") from error

    print(
        f"VIC shadow ${result['shadow_start']:04X}-${result['shadow_end']:04X}; "
        f"free payload holes: {len(result['holes'])}"
    )
    for name, start, end in result["holes"]:
        print(f"  {name:18s} ${start:04X}-${end:04X}  {end - start + 1:5d}")
    print(
        f"total free {result['hole_total']} bytes; "
        f"largest contiguous {result['largest_hole']} bytes"
    )
    for name, size in result["objects"].items():
        fit = result["fits"][name]
        print(
            f"  {name:24s} {size:5d} bytes; "
            f"single hole: {fit['single_hole']}; "
            f"aggregate: {fit['aggregate']}"
        )
    if args.check:
        for name, fit in result["fits"].items():
            if fit["aggregate"]:
                raise SystemExit(
                    f"{name} now fits the free payload holes; update "
                    "docs/BOOT-STAGING-MAP.md and the relocation plan"
                )
        print("boot staging map OK")


if __name__ == "__main__":
    main()

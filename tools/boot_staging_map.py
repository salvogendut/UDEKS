#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Byte-accurate bank-0 staging/lifetime map for the boot-only objects.

The map is derived from the linker map, the emitted staging artifacts, the
installer copy lengths, and the payload staging containers in
tools/build_d71.py.  It distinguishes:

- emitted bytes: the live artifact the installer transfers,
- copied bytes: the range the installer actually reads (a container page or
  the emitted length, whichever the installer uses),
- container bytes: the padded build_d71 reservation, which may extend past the
  copied range and leave a free hole.

It reports where the staged boot-only images live, the free payload holes that
could hold another staged image, the copied-but-dead padding, and whether the
remaining boot-only objects fit.
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
    BOOTFS_Z80_SIZE,
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
STAGE1_CODE_END = 0x1FAA
STAGE1_SPRITE_START = 0x1FC0
Z80_CODE_END = 0xD296
Z80_STAGING_BASE = 0xD000
Z80_STAGING_LIMIT = 0xF000
BOOT_ONLY_OBJECTS = ("hardware_capability.o", "boot_console.o")

ARTIFACT_FILES = {
    "bootfs": "build/user/bootfs.img",
    "module": "build/8502/udeks-module.bin",
    "task_request": "build/boot/task-request-gateway.bin",
    "bootfs_request": "build/boot/bootfs-request-service.bin",
    "task_loader": "build/boot/task-loader.bin",
    "task_gate": "build/boot/task-bank-gateway.bin",
}


@dataclass(frozen=True)
class StagedRegion:
    name: str
    start: int
    copied_size: int
    container_size: int
    emitted_size: int
    live: str

    @property
    def copied_end(self) -> int:
        return self.start + self.copied_size - 1

    @property
    def emitted_end(self) -> int:
        return self.start + self.emitted_size - 1

    @property
    def container_end(self) -> int:
        return self.start + self.container_size - 1

    @property
    def padding(self) -> int:
        return max(0, self.copied_size - self.emitted_size)


def staged_regions(emitted: dict[str, int]) -> list[StagedRegion]:
    """Staging regions with the installer's actual copied lengths."""
    emitted = dict(emitted)
    if "bootfs_tail" not in emitted:
        if "bootfs" not in emitted:
            raise ValueError("bootfs artifact size is required")
        emitted["bootfs_tail"] = emitted["bootfs"] - BOOTFS_Z80_SIZE
    return [
        StagedRegion(
            "probe staging",
            PROBE_STAGING_ADDRESS,
            PROBE_SIZE,
            PROBE_SIZE,
            emitted["probe"],
            "load..crt0",
        ),
        StagedRegion(
            "crt0 staging",
            CRT0_STAGING_ADDRESS,
            CRT0_SIZE,
            CRT0_SIZE,
            emitted["crt0"],
            "load..crt0",
        ),
        StagedRegion(
            "bootfs tail staging",
            BOOTFS_TAIL_STAGING_ADDRESS,
            BOOTFS_TAIL_SIZE,
            BOOTFS_TAIL_SIZE,
            emitted["bootfs_tail"],
            "load..stage1",
        ),
        StagedRegion(
            "module staging",
            MODULE_STAGING_ADDRESS,
            MODULE_STAGING_SIZE,
            MODULE_STAGING_SIZE,
            emitted["module"],
            "load..stage1",
        ),
        StagedRegion(
            "task request staging",
            TASK_REQUEST_STAGING_ADDRESS,
            TASK_REQUEST_STAGING_SIZE,
            TASK_REQUEST_STAGING_SIZE,
            emitted["task_request"],
            "load..stage1",
        ),
        StagedRegion(
            "bootfs request staging",
            BOOTFS_REQUEST_STAGING_ADDRESS,
            # The final installer copies two pages plus $9B bytes, the linked
            # $029B reservation, not the $0311 padded container.
            emitted["bootfs_request"],
            BOOTFS_REQUEST_STAGING_SIZE,
            emitted["bootfs_request"],
            "load..stage1",
        ),
        StagedRegion(
            "task loader staging",
            TASK_LOADER_STAGING_ADDRESS,
            TASK_LOADER_STAGING_SIZE,
            TASK_LOADER_STAGING_SIZE,
            emitted["task_loader"],
            "load..stage1",
        ),
        StagedRegion(
            "task gate staging",
            TASK_BANK_GATE_STAGING_ADDRESS,
            TASK_BANK_GATE_STAGING_SIZE,
            TASK_BANK_GATE_STAGING_SIZE,
            emitted["task_gate"],
            "load..stage1",
        ),
    ]


def shadow_bounds(map_text: str) -> tuple[int, int]:
    _, segments = parse_map(map_text)
    for name, start, end in segments:
        if name == VIC_SHADOW_SEGMENT:
            return start, end
    raise ValueError(f"{VIC_SHADOW_SEGMENT} segment is missing from the map")


def segment_bounds(map_text: str, name: str) -> tuple[int, int]:
    _, segments = parse_map(map_text)
    for segment_name, start, end in segments:
        if segment_name == name:
            return start, end
    raise ValueError(f"{name} segment is missing from the map")


def stage0_end(stage0: bytes) -> int:
    last = max(
        (offset for offset, byte in enumerate(stage0) if byte),
        default=0,
    )
    return BOOT_SECTOR_BASE + last


def free_holes(
    shadow_start: int,
    stage0_last: int,
    regions: list[StagedRegion],
) -> list[tuple[str, int, int]]:
    """Payload byte ranges that can hold another staged boot-only image."""
    holes: list[tuple[str, int, int]] = []
    window_end = SYSCALL_PAGE - 1
    cursor = shadow_start
    for region in sorted(regions, key=lambda item: item.start):
        if region.copied_end < shadow_start or region.start > window_end:
            continue
        if region.start > cursor:
            holes.append(("staging hole", cursor, region.start - 1))
        cursor = max(cursor, region.copied_end + 1)
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


def unowned_padding() -> list[tuple[str, int, int, str]]:
    """Copied or reserved padding whose ownership is not frozen yet."""
    return [
        (
            "stage-1 code padding",
            STAGE1_CODE_END + 1,
            STAGE1_SPRITE_START - 1,
            "copied dead stage-1 page padding",
        ),
        (
            "z80 tail padding",
            Z80_CODE_END + 1,
            Z80_STAGING_BASE + 0x2FF,
            "copied into bank 1, not available until ownership is frozen",
        ),
    ]


def artifact_sizes(root: Path) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for name, relative in ARTIFACT_FILES.items():
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing staging artifact: {relative}")
        sizes[name] = path.stat().st_size
    sizes["bootfs_tail"] = sizes["bootfs"] - BOOTFS_Z80_SIZE
    if sizes["bootfs_tail"] <= 0:
        raise ValueError("bootfs is smaller than its Z80 staging part")
    return sizes


def object_sizes(map_text: str) -> dict[str, dict[str, int]]:
    modules, _ = parse_map(map_text)
    sizes: dict[str, dict[str, int]] = {}
    for name in BOOT_ONLY_OBJECTS:
        segments = modules.get(name, {})
        code = module_code_size(segments)
        bss = module_bss_size(segments)
        sizes[name] = {
            "staged": code,
            "runtime": code + bss,
        }
    return sizes


def analyze(
    map_text: str,
    stage0: bytes,
    emitted: dict[str, int],
) -> dict[str, object]:
    shadow_start, shadow_end = shadow_bounds(map_text)
    probe_start, probe_end = segment_bounds(map_text, "PROBECODE")
    startup_start, startup_end = segment_bounds(map_text, "STARTUP")
    emitted = dict(emitted)
    emitted["probe"] = probe_end - probe_start + 1
    emitted["crt0"] = startup_end - startup_start + 1
    regions = staged_regions(emitted)
    holes = free_holes(shadow_start, stage0_end(stage0), regions)
    sizes = object_sizes(map_text)
    largest = max((end - start + 1 for _, start, end in holes), default=0)
    total = sum(end - start + 1 for _, start, end in holes)
    fits = {
        name: {
            "single_hole": values["staged"] <= largest,
            "aggregate": values["staged"] <= total,
        }
        for name, values in sizes.items()
    }
    return {
        "shadow_start": shadow_start,
        "shadow_end": shadow_end,
        "holes": holes,
        "hole_total": total,
        "largest_hole": largest,
        "objects": sizes,
        "fits": fits,
        "padding": [
            {
                "name": region.name,
                "start": region.start + region.emitted_size,
                "end": region.copied_end,
                "size": region.padding,
                "note": "copied but dead; ownership not frozen",
            }
            for region in regions
            if region.padding
            and not any(
                other is not region
                and other.start
                <= region.start + region.emitted_size
                <= other.emitted_end
                for other in regions
            )
        ],
        "unowned_padding": unowned_padding(),
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
            args.map.read_text(encoding="utf-8"),
            args.stage0.read_bytes(),
            artifact_sizes(ROOT),
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
    for name, values in result["objects"].items():
        fit = result["fits"][name]
        print(
            f"  {name:24s} staged {values['staged']:5d}; "
            f"runtime {values['runtime']:5d}; "
            f"single hole: {fit['single_hole']}; "
            f"aggregate: {fit['aggregate']}"
        )
    for padding in result["padding"]:
        print(
            f"  padding {padding['name']:24s} "
            f"${padding['start']:04X}-${padding['end']:04X} "
            f"{padding['size']:5d} ({padding['note']})"
        )
    for name, start, end, note in result["unowned_padding"]:
        print(
            f"  unowned {name:24s} ${start:04X}-${end:04X} "
            f"{end - start + 1:5d} ({note})"
        )
    if args.check:
        for name, fit in result["fits"].items():
            if fit["single_hole"]:
                raise SystemExit(
                    f"{name} now fits a contiguous payload hole; update "
                    "docs/BOOT-STAGING-MAP.md and the relocation plan"
                )
        print("boot staging map OK")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit the resident 8502 linker map for the scheduler placement budget.

All linked-segment ends are inclusive. Gateway sizes come from the absolute
`_udeks_vic_gateway_size_*` exports in the assembled vic_graphics_transport
object, read with od65; nothing is hardcoded.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from bench_decode import parse_number


ROOT = Path(__file__).resolve().parents[1]

KERNEL_BASE = 0x2000
KERNEL_LIMIT = 0xD000
SYSCALL_PAGE = 0xCF00
VIC_SHADOW_SEGMENT = "VICSHADOW"
BOOTSTRAP_BASE = 0x1C00
BOOTSTRAP_SIZE = 0x0400

COMMON_GATEWAY = 0xF68A
TRANSIENT_STACK_BASE = 0xF700
TRANSIENT_STACK_LIMIT = 0xF800
BOOTFS_BASE = 0xF3EF
BOOTFS_LIMIT = 0xF682
REQUEST_GATEWAY_BASE = 0xF800
REQUEST_GATEWAY_LIMIT = 0xF910
TASK_LOADER_BASE = 0xF910
TASK_LOADER_LIMIT = 0xFF00
TASK_GATE_BASE = 0xFF05
TASK_GATE_END = 0xFFC4
TASK_GATE_LIMIT = 0xFFC5
HIGH_RESERVED_BASE = 0xF800
GATEWAY_QUALIFIED_END = 0xF7EF
GATEWAY_SIZE_BASELINE = (254, 46, 68, 358)

GATEWAY_SIZE_SUFFIXES = ("vic", "sprite", "page", "outline")

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

DATA_SEGMENTS = (
    "STARTUP", "LOWCODE", "ONCE", "CODE", "RODATA", "DATA", "BSS",
)


def parse_map(text: str) -> tuple[dict[str, dict[str, int]], list[tuple[str, int, int]]]:
    modules: dict[str, dict[str, int]] = {}
    segments: list[tuple[str, int, int]] = []

    current = None
    section = "modules"
    for line in text.splitlines():
        if line.startswith("Segment list:"):
            section = "segments"
            current = None
            continue
        if line.startswith("Exports list"):
            section = "exports"
            continue
        if section == "modules":
            match = re.match(r"^(\S+):$", line)
            if match:
                current = match.group(1)
                modules.setdefault(current, {})
                continue
            match = re.match(
                r"^\s+(\S+)\s+Offs=[0-9A-Fa-f]+\s+Size=([0-9A-Fa-f]+)", line
            )
            if match and current is not None:
                modules[current][match.group(1)] = int(match.group(2), 16)
        elif section == "segments":
            match = re.match(
                r"^(\S+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)",
                line,
            )
            if match:
                segments.append(
                    (
                        match.group(1),
                        int(match.group(2), 16),
                        int(match.group(3), 16),
                    )
                )
    return modules, segments


def module_code_size(segments: dict[str, int]) -> int:
    return sum(
        size for name, size in segments.items() if name in CODE_SEGMENTS
    )


def module_bss_size(segments: dict[str, int]) -> int:
    return sum(size for name, size in segments.items() if "BSS" in name)


def sizes_from_object_dump(text: str) -> list[int] | None:
    values: dict[str, int] = {}
    for match in re.finditer(
        r'Name:\s+"_udeks_vic_gateway_size_(\w+)"\s*\n\s*'
        r"Value:\s+0x([0-9A-Fa-f]+)",
        text,
    ):
        values[match.group(1)] = int(match.group(2), 16)
    if any(suffix not in values for suffix in GATEWAY_SIZE_SUFFIXES):
        return None
    return [values[suffix] for suffix in GATEWAY_SIZE_SUFFIXES]


def ranges_overlap(
    first: tuple[int, int], second: tuple[int, int]
) -> bool:
    return first[0] <= second[1] and second[0] <= first[1]


def reserved_common_ranges(gateway_end: int | None) -> list[tuple[str, int, int]]:
    ranges = [
        ("bootfs request service", BOOTFS_BASE, BOOTFS_LIMIT - 1),
        ("request gateway", REQUEST_GATEWAY_BASE, REQUEST_GATEWAY_LIMIT - 1),
        ("transient task stack", TRANSIENT_STACK_BASE, TRANSIENT_STACK_LIMIT - 1),
        ("task loader", TASK_LOADER_BASE, TASK_LOADER_LIMIT - 1),
        ("bank-1 task gate", TASK_GATE_BASE, TASK_GATE_LIMIT - 1),
    ]
    if gateway_end is not None:
        ranges.append(("VIC common gateways", COMMON_GATEWAY, gateway_end))
    return ranges


def vic_bitmap_size() -> int:
    header = (ROOT / "include/udeks/vic_graphics.h").read_text(encoding="utf-8")
    match = re.search(
        r"^#define\s+UDEKS_VIC_BITMAP_SIZE\s+(\d+)u?$", header, re.MULTILINE
    )
    if match is None:
        raise ValueError("UDEKS_VIC_BITMAP_SIZE is missing")
    return int(match.group(1))


def audit(
    map_text: str, object_dump: str | None = None
) -> dict[str, object]:
    modules, segments = parse_map(map_text)
    by_name = {name: (start, end) for name, start, end in segments}

    data_end = max(
        end for name, _, end in segments if name in DATA_SEGMENTS
    )
    shadow = by_name.get(VIC_SHADOW_SEGMENT)
    if shadow is None:
        raise ValueError("VICSHADOW segment is missing")
    shadow_start, shadow_end = shadow
    shadow_size = shadow_end - shadow_start + 1
    padding = shadow_size - vic_bitmap_size()

    sizes = sizes_from_object_dump(object_dump) if object_dump else None
    if sizes is None:
        gateway_end = None
        gateway_total = None
        gateway_high_overlap: list[str] = []
    else:
        gateway_total = max(sizes)
        gateway_end = COMMON_GATEWAY + gateway_total - 1
        gateway_high_overlap = [
            suffix
            for suffix, size in zip(GATEWAY_SIZE_SUFFIXES, sizes)
            if ranges_overlap(
                (COMMON_GATEWAY, COMMON_GATEWAY + size - 1),
                (HIGH_RESERVED_BASE, 0xFFFF),
            )
        ]

    boot_only = {}
    for name in BOOT_ONLY_OBJECTS:
        segments_for_object = modules.get(name, {})
        boot_only[name] = (
            module_code_size(segments_for_object)
            + module_bss_size(segments_for_object)
        )

    kernel_used = data_end - KERNEL_BASE + 1
    kernel_gap = shadow_start - (data_end + 1)
    free_after_shadow = max(0, SYSCALL_PAGE - (shadow_start + shadow_size))
    reclaim_total = (
        sum(boot_only.values())
        + kernel_gap
        + padding
        + free_after_shadow
        + BOOTSTRAP_SIZE
    )

    boot_page = (TRANSIENT_STACK_BASE, TRANSIENT_STACK_LIMIT - 1)
    boot_page_overlaps = [
        name
        for name, start, end in reserved_common_ranges(gateway_end)
        if ranges_overlap(boot_page, (start, end))
    ]
    uncontested_boot_page = 0
    if gateway_end is not None:
        first_free = max(gateway_end + 1, TRANSIENT_STACK_LIMIT)
        if first_free < TRANSIENT_STACK_LIMIT:
            uncontested_boot_page = TRANSIENT_STACK_LIMIT - first_free

    return {
        "kernel_base": KERNEL_BASE,
        "data_end": data_end,
        "kernel_used": kernel_used,
        "kernel_gap": kernel_gap,
        "vic_shadow_start": shadow_start,
        "vic_shadow_size": shadow_size,
        "vic_shadow_padding": padding,
        "free_after_shadow": free_after_shadow,
        "gateway_sizes": sizes,
        "gateway_total": gateway_total,
        "gateway_end": gateway_end,
        "boot_only": boot_only,
        "boot_only_total": sum(boot_only.values()),
        "bootstrap_bytes": BOOTSTRAP_SIZE,
        "reclaim_total": reclaim_total,
        "reserved_common": [
            {"name": name, "base": start, "end": end}
            for name, start, end in reserved_common_ranges(gateway_end)
        ],
        "boot_page_overlaps": boot_page_overlaps,
        "uncontested_boot_page_bytes": uncontested_boot_page,
        "task_gate": (
            {
                "base": by_name["TASKGATE"][0],
                "end": by_name["TASKGATE"][1],
                "size": by_name["TASKGATE"][1] - by_name["TASKGATE"][0] + 1,
            }
            if "TASKGATE" in by_name
            else None
        ),
        "gateway_high_overlap": gateway_high_overlap,
        "largest_objects": sorted(
            (
                {
                    "name": name,
                    "code": module_code_size(values),
                    "bss": module_bss_size(values),
                    "total": module_code_size(values) + module_bss_size(values),
                }
                for name, values in modules.items()
            ),
            key=lambda row: row["total"],
            reverse=True,
        )[:10],
    }


def verify(result: dict[str, object]) -> list[str]:
    failures: list[str] = []
    sizes = result["gateway_sizes"]
    if sizes is None:
        failures.append(
            "gateway sizes unavailable; build the object and run od65 in the "
            "reference container"
        )
    else:
        if tuple(sizes) != GATEWAY_SIZE_BASELINE:
            failures.append(
                f"gateway sizes {sizes} changed from the qualified baseline "
                f"{list(GATEWAY_SIZE_BASELINE)}; update "
                "docs/SCHEDULER-PLACEMENT.md"
            )
        if result["gateway_end"] > GATEWAY_QUALIFIED_END:
            failures.append(
                f"gateway copies reach ${result['gateway_end']:04X}, beyond "
                f"the qualified ${GATEWAY_QUALIFIED_END:04X}"
            )
        if result["gateway_high_overlap"]:
            failures.append(
                "gateway copies overlap $F800 and later reserved ranges "
                f"({', '.join(result['gateway_high_overlap'])})"
            )
    if result["vic_shadow_padding"] != 0:
        failures.append(
            f"VICSHADOW reserves {result['vic_shadow_padding']} padding bytes "
            "beyond UDEKS_VIC_BITMAP_SIZE; link it at its bitmap size"
        )
    if result["kernel_gap"] != 0:
        failures.append(
            f"VICSHADOW starts {result['kernel_gap']} bytes after BSS; "
            "link it sequentially"
        )
    if result["uncontested_boot_page_bytes"] != 0:
        failures.append(
            "boot-page overlap expectation changed; update "
            "docs/SCHEDULER-PLACEMENT.md"
        )
    for name in ("VIC common gateways", "transient task stack"):
        if name not in result["boot_page_overlaps"]:
            failures.append(f"expected {name} to overlap the boot page")
    gate = result["task_gate"]
    if gate is None:
        failures.append("TASKGATE segment is missing from the linker map")
    elif gate["base"] != TASK_GATE_BASE or gate["end"] != TASK_GATE_END:
        failures.append(
            f"TASKGATE moved to ${gate['base']:04X}-${gate['end']:04X}; "
            f"expected ${TASK_GATE_BASE:04X}-${TASK_GATE_END:04X}"
        )
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "map", type=Path,
        nargs="?",
        default=ROOT / "build/8502/udeks-8502.map",
        help="ld65 map file (default: build/8502/udeks-8502.map)",
    )
    parser.add_argument(
        "--object", type=Path,
        default=ROOT / "build/8502/vic_graphics_transport.o",
        help="assembled VIC transport object holding the gateway sizes",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--verify", action="store_true",
        help="fail unless the real gateway sizes and overlap expectations hold",
    )
    args = parser.parse_args()

    if args.verify and shutil.which("od65") is None:
        print(
            "placement-check requires cc65/od65; run it inside the reference "
            "container:"
        )
        print("  distrobox enter my-distrobox -- make placement-check")
        raise SystemExit(1)

    object_dump = None
    if args.object.exists() and shutil.which("od65"):
        object_dump = subprocess.run(
            ["od65", "--dump-exports", str(args.object)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    try:
        result = audit(args.map.read_text(encoding="utf-8"), object_dump)
    except (OSError, ValueError) as error:
        raise SystemExit(f"placement audit failed: {error}") from error

    if args.verify:
        failures = verify(result)
        if failures:
            for failure in failures:
                print(f"placement audit failed: {failure}")
            raise SystemExit(1)
        print("placement audit OK")
        return

    if args.json:
        print(json.dumps(result, indent=2))
        return
    shadow_end = result["vic_shadow_start"] + result["vic_shadow_size"] - 1
    print(
        f"Bank-0 data ends at ${result['data_end']:04X} "
        f"({result['kernel_used']} bytes); "
        f"VIC shadow ${result['vic_shadow_start']:04X}-${shadow_end:04X} "
        f"({result['vic_shadow_size']} bytes)"
    )
    print(
        f"Gap before shadow {result['kernel_gap']} bytes; "
        f"free after shadow {result['free_after_shadow']} bytes; "
        f"padding {result['vic_shadow_padding']} bytes"
    )
    print(f"Boot-only objects {result['boot_only_total']} bytes")
    for name, size in result["boot_only"].items():
        print(f"  {name:24s} {size:5d}")
    print(f"Total bank-0 reclaim: {result['reclaim_total']} bytes")
    if result["gateway_sizes"] is None:
        print("VIC gateway sizes: unavailable (build and run od65 first)")
    else:
        print(
            f"VIC gateways {result['gateway_sizes']}; "
            f"copy ${COMMON_GATEWAY:04X}-${result['gateway_end']:04X}"
        )
    print(
        f"Boot page $F700-$F7FF overlaps: "
        f"{', '.join(result['boot_page_overlaps']) or 'none'}; "
        f"uncontested bytes {result['uncontested_boot_page_bytes']}"
    )
    gate = result["task_gate"]
    if gate is None:
        print("Legacy bank-1 task gate: missing from the map")
    else:
        print(
            f"Legacy bank-1 task gate: {gate['size']} bytes "
            f"(${gate['base']:04X}-${gate['end']:04X})"
        )


if __name__ == "__main__":
    main()

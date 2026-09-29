#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the input smoke harness against an unmodified sibling 1986 tree."""
import argparse
from pathlib import Path
import shlex
import subprocess
import re
import os


def emulator_sources(emulator: Path) -> list[Path]:
    source_list = (emulator / "Makefile.am").read_text().split("1986_SOURCES =", 1)[1].split("noinst_HEADERS", 1)[0]
    return [emulator / word for word in source_list.replace("\\", " ").split()
            if word.endswith(".c") and word != "src/main.c"]


def slot_address(map_path: Path) -> str:
    match = re.search(r"_udeks_lifecycle_slots_private\s+([0-9A-Fa-f]{6})\s+RLA", map_path.read_text())
    if not match:
        raise ValueError("scheduler map lacks the task-slot binding")
    return "0x" + match[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emulator", type=Path, default=Path("../1986"))
    parser.add_argument("--output", type=Path, default=Path("build/1986-input-smoke"))
    parser.add_argument("--roms", type=Path, help="also run using locally owned ROMs")
    parser.add_argument("--disk", type=Path, default=Path("build/boot/udeks.d71"))
    parser.add_argument("--map", type=Path, default=Path("build/8502/udeks-scheduler-overlay.map"))
    parser.add_argument("--snapshot", type=Path, default=Path("build/1986-input-smoke.vsf"))
    parser.add_argument("--log", type=Path, help="save stdout/stderr, including failures")
    parser.add_argument("--drag-stress", type=int,
                        help="repeat wave drags (minimum 16), half partial/half cached")
    parser.add_argument("--drag-clock", action="store_true",
                        help="run a background clock during --drag-stress")
    args = parser.parse_args()
    if args.drag_stress is not None and args.drag_stress < 16:
        parser.error("--drag-stress must be at least 16 to cover every byte alignment")
    if args.drag_clock and args.drag_stress is None:
        parser.error("--drag-clock requires --drag-stress")
    emulator = args.emulator.resolve()
    flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs", "sdl3"], text=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cc", "-std=gnu11", "-O2", "-I" + str(emulator / "src"),
                    "tools/1986_input_smoke.c", *map(str, emulator_sources(emulator)),
                    *flags, "-lm", "-o", str(args.output)], check=True)
    if args.roms:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        if args.drag_stress is not None:
            environment["UDEKS_DRAG_STRESS"] = str(args.drag_stress)
        if args.drag_clock:
            environment["UDEKS_DRAG_CLOCK"] = "1"
        result = subprocess.run([str(args.output.resolve()), str(args.roms.resolve()),
                                 str(args.disk.resolve()), slot_address(args.map),
                                 str(args.snapshot.resolve())], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=environment)
        print(result.stdout, end="")
        if args.log:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            args.log.write_text(result.stdout)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

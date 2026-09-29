#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify bounded SLEEP rejection, blocking, timed wake, and resume."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shadow_boot_probe as sp
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, monitor_command


ROOT = Path(__file__).resolve().parents[1]
PROBE = 0xF040
PHASE = PROBE + 4


def run(disk: Path, overlay_map: Path, timeout: float, flatpak_id: str) -> None:
    symbols = scheduler_symbols(overlay_map)
    slots = symbols["_udeks_lifecycle_slots_private"]
    wait_state = symbols["_udeks_task_wait_state_private"]
    match = re.search(
        r"_udeks_monotonic_ticks_low\s+([0-9A-Fa-f]{6})\s+RLA",
        overlay_map.read_text(encoding="utf-8"),
    )
    if match is None:
        raise RuntimeError("scheduler map lacks the monotonic counter")
    tick_low = int(match.group(1), 16)
    port = choose_port()
    deadline = time.monotonic() + timeout
    process, master_fd = sp.launch_vice(disk.resolve(), port, flatpak_id)
    work = ROOT / "build/vice"
    work.mkdir(parents=True, exist_ok=True)
    try:
        print(f"{disk.name}: booting SLEEP task", flush=True)
        sp.wait_for_byte(port, PHASE, 1, deadline)
        start = sp.capture_blocks(
            port, [(work / "task-sleep-start.bin", tick_low, tick_low + 1, "kernel")]
        )[0]
        monitor_command(port, f"> {PROBE + 15:04x} 5a")
        sp.wait_for_byte(port, slots + 1, 4, deadline)
        blocked = sp.capture_blocks(
            port,
            [
                (work / "task-sleep-blocked-slot.bin", slots, slots + 7, "kernel"),
                (work / "task-sleep-blocked-wait.bin", wait_state, wait_state + 7, "kernel"),
            ],
        )
        if blocked[0][1:3] != bytes((4, 3)) or blocked[1][0] != 1:
            raise RuntimeError("SLEEP did not publish WAITING/TIMER ownership")
        sp.wait_for_byte(port, PHASE, 0xA5, deadline)
        record, end = sp.capture_blocks(
            port,
            [
                (work / "task-sleep-record.bin", PROBE, PROBE + 15, "kernel"),
                (work / "task-sleep-end.bin", tick_low, tick_low + 1, "kernel"),
            ],
        )
        if record[:5] != b"USL0\xA5":
            raise RuntimeError(f"SLEEP record incomplete: {record[:5]!r}")
        if record[5:8] != bytes((0x80, 22, 0x71)):
            raise RuntimeError(f"SLEEP(0) response is {record[5:8].hex()}")
        if record[8:11] != bytes((0x80, 22, 0x72)):
            raise RuntimeError(f"SLEEP(601) response is {record[8:11].hex()}")
        if record[11:15] != bytes((2, 0, 0, 0x73)):
            raise RuntimeError(f"SLEEP(600) response is {record[11:15].hex()}")
        start_tick = int.from_bytes(start, "little")
        end_tick = int.from_bytes(end, "little")
        elapsed = (end_tick - start_tick) & 0xFFFF
        if elapsed < 600 or elapsed >= 0x8000:
            raise RuntimeError(f"SLEEP resumed after {elapsed} logical ticks")
        print(
            f"{disk.name}: invalid 0/601 rejected; SLEEP(600) blocked and "
            f"resumed after {elapsed} logical ticks",
            flush=True,
        )
    finally:
        sp.terminate(process, port)
        try:
            os.close(master_fd)
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--disk", type=Path,
        default=ROOT / "build/boot/udeks-task-sleep-probe.d71",
    )
    parser.add_argument(
        "--map", type=Path,
        default=ROOT / "build/8502/udeks-scheduler-overlay.map",
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    try:
        run(args.disk, args.map, args.timeout, args.flatpak_id)
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        raise SystemExit(f"task-SLEEP probe failed: {error}") from error
    print("task-SLEEP probe OK")


if __name__ == "__main__":
    main()

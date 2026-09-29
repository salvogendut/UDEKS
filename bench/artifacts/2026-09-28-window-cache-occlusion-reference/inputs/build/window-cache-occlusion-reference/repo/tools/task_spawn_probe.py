#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify SPAWN, implicit EXIT, blocking WAITPID, and task-2 reuse."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shadow_boot_probe as sp
from task_waitpid_probe import context_symbols, scheduler_symbols
from vice_capture import choose_port, monitor_command


ROOT = Path(__file__).resolve().parents[1]
PROBE = 0xF040
PROBE_PHASE = PROBE + 4
PHASE_COMPLETE = 0xA5
HANDLER_ADDRESS = 0xC900
TASK_SLOT_SIZE = 8
TASK_CONTEXT_SIZE = 11
RETURN_TRAMPOLINE = 0xF280


def probe_disk(
    disk: Path,
    map_path: Path,
    context_map_path: Path,
    handler_path: Path,
    timeout: float,
    flatpak_id: str,
) -> None:
    symbols = scheduler_symbols(map_path)
    contexts = context_symbols(context_map_path)
    slots = symbols["_udeks_lifecycle_slots_private"]
    current = symbols["_udeks_lifecycle_current_private"]
    wait_state = symbols["_udeks_task_wait_state_private"]
    context_table = contexts["_udeks_task_contexts_private"]
    handler = handler_path.read_bytes()
    deadline = time.monotonic() + timeout
    port = choose_port()
    process, master_fd = sp.launch_vice(disk.resolve(), port, flatpak_id)
    try:
        print(f"{disk.name}: booting SPAWN parent", flush=True)
        work = ROOT / "build/vice"
        work.mkdir(parents=True, exist_ok=True)
        try:
            sp.wait_for_byte(port, PROBE_PHASE, PHASE_COMPLETE, deadline)
        except TimeoutError as error:
            registers = monitor_command(port, "r").decode("ascii", errors="replace")
            live_stack = monitor_command(port, "m 01f0 01ff").decode(
                "ascii", errors="replace"
            )
            diagnostic = sp.capture_blocks(
                port,
                [
                    (work / "task-spawn-timeout-record.bin", PROBE, PROBE + 31, "kernel"),
                    (
                        work / "task-spawn-timeout-request.bin",
                        0xF359,
                        0xF37E,
                        "kernel",
                    ),
                    (
                        work / "task-spawn-timeout-lifecycle.bin",
                        slots,
                        current,
                        "kernel",
                    ),
                    (
                        work / "task-spawn-timeout-context.bin",
                        context_table,
                        context_table + 2 * TASK_CONTEXT_SIZE - 1,
                        "kernel",
                    ),
                    (
                        work / "task-spawn-timeout-child.bin",
                        0x0200,
                        0x021F,
                        "worker",
                    ),
                    (
                        work / "task-spawn-timeout-return.bin",
                        RETURN_TRAMPOLINE,
                        RETURN_TRAMPOLINE + 31,
                        "kernel",
                    ),
                    (
                        work / "task-spawn-timeout-stack.bin",
                        0xD4F0,
                        0xD4FF,
                        "worker",
                    ),
                    (
                        work / "task-spawn-timeout-return-frame.bin",
                        0xF2A0,
                        0xF2A2,
                        "kernel",
                    ),
                    (
                        work / "task-spawn-timeout-live-context.bin",
                        0xFFB9,
                        0xFFC3,
                        "kernel",
                    ),
                ],
            )
            raise RuntimeError(
                f"SPAWN probe timed out ({registers.strip()}; "
                f"stack {live_stack.strip()}): "
                + ", ".join(block.hex() for block in diagnostic)
            ) from error
        record, lifecycle, pending, context, frame, trampoline, installed = sp.capture_blocks(
            port,
            [
                (work / "task-spawn-record.bin", PROBE, PROBE + 32, "kernel"),
                (work / "task-spawn-lifecycle.bin", slots, current, "kernel"),
                (work / "task-spawn-pending.bin", wait_state, wait_state + 7, "kernel"),
                (
                    work / "task-spawn-context.bin",
                    context_table + TASK_CONTEXT_SIZE,
                    context_table + 2 * TASK_CONTEXT_SIZE - 1,
                    "kernel",
                ),
                (
                    work / "task-spawn-return-frame.bin",
                    0xF2A0,
                    0xF2A2,
                    "kernel",
                ),
                (
                    work / "task-spawn-return.bin",
                    RETURN_TRAMPOLINE,
                    RETURN_TRAMPOLINE + 31,
                    "kernel",
                ),
                (
                    work / "task-spawn-handler.bin",
                    HANDLER_ADDRESS,
                    HANDLER_ADDRESS + len(handler) - 1,
                    "kernel",
                ),
            ],
        )
        if record[:5] != b"USP0\xA5":
            raise RuntimeError(f"SPAWN probe record is incomplete: {record[:5]!r}")
        if record[5:11] != bytes((2, 1, 0, 0x33, 2, 0)):
            raise RuntimeError(f"SPAWN response is {record[5:11].hex()}")
        if record[11:19] != bytes((2, 1, 0, 0x44, 2, 0, 37, 0)):
            raise RuntimeError(f"WAITPID response is {record[11:19].hex()}")
        if record[19:25] != bytes((2, 1, 0, 0x55, 2, 0)):
            raise RuntimeError(f"second SPAWN response is {record[19:25].hex()}")
        if record[25:33] != bytes((2, 1, 0, 0x66, 2, 0, 37, 0)):
            raise RuntimeError(f"second WAITPID response is {record[25:33].hex()}")
        if lifecycle[TASK_SLOT_SIZE : 2 * TASK_SLOT_SIZE] != bytes(TASK_SLOT_SIZE):
            raise RuntimeError("reaped SPAWN child slot was not completely cleared")
        if lifecycle[-1] != 1:
            raise RuntimeError("SPAWN parent is no longer the running task")
        if pending[0] != 0:
            raise RuntimeError("published parent WAITPID snapshot was not released")
        expected_context = bytes((0, 0, 0, 0x24, 0xFF, 0x80, 0xF2, 0xD3, 1, 0xD4, 1))
        if context != expected_context:
            raise RuntimeError(f"task-2 initial context is {context.hex()}")
        if frame != b"\x82\xf2\xfd":
            raise RuntimeError(f"task-entry return frame is {frame.hex()}")
        if trampoline[:3] != b"\x20\x00\x02":
            raise RuntimeError("task-return trampoline has an invalid entry")
        if b"\x20\x16\xff" not in trampoline:
            raise RuntimeError("task-return trampoline does not call $FF16")
        if installed != handler:
            raise RuntimeError("permanent lifecycle handler differs from linked image")
        print(
            f"{disk.name}: two SPAWN -> compiled task 2 cycles, normal return "
            "-> EXIT(37), blocking WAITPID reaped/resumed sequences $44/$66",
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
        "--disk",
        type=Path,
        default=ROOT / "build/boot/udeks-task-spawn-probe.d71",
    )
    parser.add_argument(
        "--map",
        type=Path,
        default=ROOT / "build/8502/udeks-scheduler-overlay.map",
    )
    parser.add_argument(
        "--context-map",
        type=Path,
        default=ROOT / "build/8502/task-context-binding.map",
    )
    parser.add_argument(
        "--handler",
        type=Path,
        default=ROOT / "build/8502/task-yield-handler.bin",
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    try:
        probe_disk(
            args.disk,
            args.map,
            args.context_map,
            args.handler,
            args.timeout,
            args.flatpak_id,
        )
    except (KeyError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"task-SPAWN probe failed: {error}") from error
    print("task-SPAWN probe OK")


if __name__ == "__main__":
    main()

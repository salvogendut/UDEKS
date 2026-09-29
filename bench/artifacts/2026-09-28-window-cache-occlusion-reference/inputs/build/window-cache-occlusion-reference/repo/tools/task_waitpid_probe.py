#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify production nonblocking WAITPID against a monitor-seeded child."""

from __future__ import annotations

import argparse
import os
import re
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shadow_boot_probe as sp
from vice_capture import choose_port, parse_monitor_byte


ROOT = Path(__file__).resolve().parents[1]
PROBE = 0xF280
PROBE_PHASE = PROBE + 4
PHASE_READY = 1
PHASE_LIVE = 2
PHASE_ZOMBIE_READY = 3
PHASE_ZOMBIE = 4
PHASE_BLOCKING = 5
PHASE_CHILD_READY = 6
PHASE_COMPLETE = 0xA5
HANDLER_ADDRESS = 0xC900
TASK_SLOT_SIZE = 8
TASK_RUNNABLE = 2
TASK_ZOMBIE = 6
EXIT_STATUS = 37
TREQ_COMPLETE = 2
TREQ_ERROR = 0x80
ERR_ECHILD = 10


def scheduler_symbols(path: Path) -> dict[str, int]:
    wanted = {
        "_udeks_lifecycle_slots_private",
        "_udeks_lifecycle_current_private",
        "_udeks_lifecycle_last_event_private",
        "_udeks_task_wait_state_private",
    }
    found = {
        name: int(address, 16)
        for name, address in re.findall(
            r"(_udeks_lifecycle_(?:slots|current|last_event)_private|"
            r"_udeks_task_wait_state_private)\s+"
            r"([0-9A-Fa-f]{6})\s+RL[AZ]",
            path.read_text(encoding="utf-8"),
        )
    }
    if found.keys() != wanted:
        raise ValueError(f"scheduler lifecycle symbols drifted: {found!r}")
    return found


def context_symbols(path: Path) -> dict[str, int]:
    wanted = {
        "_udeks_task_contexts_private",
        "_udeks_task_context_current_private",
    }
    found = {
        name: int(address, 16)
        for name, address in re.findall(
            r"(_udeks_task_context(?:s|_current)_private)\s+"
            r"([0-9A-Fa-f]{6})\s+RL[AZ]",
            path.read_text(encoding="utf-8"),
        )
    }
    if found.keys() != wanted:
        raise ValueError(f"task-context symbols drifted: {found!r}")
    return found


def seed_child(port: int, slot: int, state: int, exit_status: int, phase: int) -> None:
    """Atomically write one bank-0 lifecycle slot, restore the live map, resume."""
    values = bytes((1, state, 0, 1, exit_status, 0, 0, 0))
    with socket.create_connection(("127.0.0.1", port), timeout=3.0) as connection:
        connection.settimeout(10.0)
        buffer = b""

        def run(command: str, marker: bytes | None = None) -> bytes:
            nonlocal buffer
            start = len(buffer)
            connection.sendall(command.encode("ascii") + b"\n")
            while True:
                fresh = buffer[start:]
                if (
                    fresh.endswith(b") ")
                    and sp.PROMPT_RE.search(fresh[-32:])
                    and (marker is None or marker in fresh)
                ):
                    return fresh
                chunk = connection.recv(4096)
                if not chunk:
                    raise RuntimeError("VICE monitor closed while seeding child")
                buffer += chunk

        mcr = parse_monitor_byte(run("m ff00 ff00", b":ff00"), 0xFF00)
        run("> ff01 00")
        for offset, value in enumerate(values):
            run(f"> {slot + offset:04x} {value:02x}")
        run(f"> ff00 {mcr:02x}")
        run(f"> {PROBE_PHASE:04x} {phase:02x}")
        connection.sendall(b"x\n")


def seed_runnable_child(port: int, slot: int, context: int) -> None:
    """Install task 2 with distinct relocated pages and a fixed EXIT entry."""
    lifecycle = bytes((1, TASK_RUNNABLE, 0, 1, 0, 0, 0, 0))
    task_context = bytes((0, 0, 0, 0x24, 0xFF, 0x00, 0x92,
                          0xD3, 1, 0xD4, 1))
    with socket.create_connection(("127.0.0.1", port), timeout=3.0) as connection:
        connection.settimeout(15.0)
        buffer = b""

        def run(command: str, marker: bytes | None = None) -> bytes:
            nonlocal buffer
            start = len(buffer)
            connection.sendall(command.encode("ascii") + b"\n")
            while True:
                fresh = buffer[start:]
                if (
                    fresh.endswith(b") ")
                    and sp.PROMPT_RE.search(fresh[-32:])
                    and (marker is None or marker in fresh)
                ):
                    return fresh
                chunk = connection.recv(4096)
                if not chunk:
                    raise RuntimeError("VICE monitor closed while installing child")
                buffer += chunk

        mcr = parse_monitor_byte(run("m ff00 ff00", b":ff00"), 0xFF00)
        page0_page = parse_monitor_byte(run("m d507 d507", b":d507"), 0xD507)
        page0_bank = parse_monitor_byte(run("m d508 d508", b":d508"), 0xD508)
        page1_page = parse_monitor_byte(run("m d509 d509", b":d509"), 0xD509)
        page1_bank = parse_monitor_byte(run("m d50a d50a", b":d50a"), 0xD50A)
        run("> ff01 00")
        for offset, value in enumerate(lifecycle):
            run(f"> {slot + offset:04x} {value:02x}")
        for offset, value in enumerate(task_context):
            run(f"> {context + offset:04x} {value:02x}")

        # Give task 2 private page zero/page one ($D3/$D4 in bank 1),
        # including the cc65 software-stack pointer and hardware-stack canary.
        run("> d508 01")
        run("> d507 d3")
        run("> d50a 01")
        run("> d509 d4")
        run("f 0000 01ff 00")
        run("> 0002 f0")
        run("> 0003 ef")
        run("> 0100 a5")
        run(f"> d508 {page0_bank:02x}")
        run(f"> d507 {page0_page:02x}")
        run(f"> d50a {page1_bank:02x}")
        run(f"> d509 {page1_page:02x}")
        run(f"> ff00 {mcr:02x}")
        run(f"> {PROBE_PHASE:04x} {PHASE_CHILD_READY:02x}")
        connection.sendall(b"x\n")


def probe_disk(disk: Path, map_path: Path, context_map_path: Path,
               handler_path: Path,
               timeout: float, flatpak_id: str) -> None:
    symbols = scheduler_symbols(map_path)
    contexts = context_symbols(context_map_path)
    slots = symbols["_udeks_lifecycle_slots_private"]
    current = symbols["_udeks_lifecycle_current_private"]
    last_event = symbols["_udeks_lifecycle_last_event_private"]
    wait_state = symbols["_udeks_task_wait_state_private"]
    context_table = contexts["_udeks_task_contexts_private"]
    if current != slots + 64:
        raise RuntimeError("lifecycle current byte moved away from the slot table")
    child = slots + TASK_SLOT_SIZE
    handler = handler_path.read_bytes()
    deadline = time.monotonic() + timeout
    port = choose_port()
    process, master_fd = sp.launch_vice(disk.resolve(), port, flatpak_id)
    try:
        print(f"{disk.name}: booting WAITPID parent", flush=True)
        sp.wait_for_byte(port, PROBE_PHASE, PHASE_READY, deadline)
        print(f"{disk.name}: parent ready", flush=True)
        seed_child(port, child, TASK_RUNNABLE, 0, PHASE_LIVE)
        sp.wait_for_byte(port, PROBE_PHASE, PHASE_ZOMBIE_READY, deadline)
        print(f"{disk.name}: NOHANG complete", flush=True)
        seed_child(port, child, TASK_ZOMBIE, EXIT_STATUS, PHASE_ZOMBIE)
        sp.wait_for_byte(port, PROBE_PHASE, PHASE_BLOCKING, deadline)
        print(f"{disk.name}: parent entering blocking wait", flush=True)
        seed_runnable_child(port, child, context_table + 11)
        sp.wait_for_byte(port, PROBE_PHASE, PHASE_COMPLETE, deadline)

        work = ROOT / "build/vice"
        work.mkdir(parents=True, exist_ok=True)
        record, lifecycle, event, pending, installed = sp.capture_blocks(
            port,
            [
                (work / "task-waitpid-record.bin", PROBE, PROBE + 27, "kernel"),
                (work / "task-waitpid-lifecycle.bin", slots, current, "kernel"),
                (work / "task-waitpid-event.bin", last_event, last_event, "kernel"),
                (work / "task-waitpid-pending.bin", wait_state, wait_state + 7, "kernel"),
                (
                    work / "task-waitpid-handler.bin",
                    HANDLER_ADDRESS,
                    HANDLER_ADDRESS + len(handler) - 1,
                    "kernel",
                ),
            ],
        )
        if record[:5] != b"UWP0\xA5":
            raise RuntimeError(f"WAITPID probe record is incomplete: {record[:5]!r}")
        if record[5:10] != bytes((TREQ_COMPLETE, 0, 0, 2, 0)):
            raise RuntimeError(f"live-child NOHANG result is {record[5:10].hex()}")
        if record[10:17] != bytes(
            (TREQ_COMPLETE, 1, 0, 2, 0, EXIT_STATUS, 0)
        ):
            raise RuntimeError(f"zombie reap result is {record[10:17].hex()}")
        if record[17:20] != bytes((TREQ_ERROR, 0, ERR_ECHILD)):
            raise RuntimeError(f"post-reap ECHILD result is {record[17:20].hex()}")
        if record[20:28] != bytes(
            (TREQ_COMPLETE, 1, 0, 0x44, 2, 0, EXIT_STATUS, 0)
        ):
            raise RuntimeError(f"blocking WAITPID result is {record[20:28].hex()}")
        if lifecycle[TASK_SLOT_SIZE:2 * TASK_SLOT_SIZE] != bytes(TASK_SLOT_SIZE):
            raise RuntimeError("reaped child slot was not completely cleared")
        if lifecycle[-1] != 1:
            raise RuntimeError("WAITPID parent is no longer the running task")
        if event != b"\x03":
            raise RuntimeError(
                f"parent was not dispatched after child reap: {event.hex()}"
            )
        if pending[0] != 0:
            raise RuntimeError("published parent wait snapshot was not released")
        if installed != handler:
            raise RuntimeError("permanent lifecycle handler differs from linked image")
        print(
            f"{disk.name}: live child -> 0, zombie 2/{EXIT_STATUS} reaped, "
            "then ECHILD; blocking child EXIT resumed sequence $44",
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
        default=ROOT / "build/boot/udeks-task-waitpid-probe.d71",
    )
    parser.add_argument(
        "--map", type=Path,
        default=ROOT / "build/8502/udeks-scheduler-overlay.map",
    )
    parser.add_argument(
        "--context-map", type=Path,
        default=ROOT / "build/8502/task-context-binding.map",
    )
    parser.add_argument(
        "--handler", type=Path,
        default=ROOT / "build/8502/task-yield-handler.bin",
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    try:
        probe_disk(
            args.disk, args.map, args.context_map, args.handler,
            args.timeout, args.flatpak_id
        )
    except (KeyError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"task-WAITPID probe failed: {error}") from error
    print("task-WAITPID probe OK")


if __name__ == "__main__":
    main()

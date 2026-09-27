#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify child-only CANCEL, blocked-request cleanup, and WAITPID status."""

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
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, parse_monitor_byte


ROOT = Path(__file__).resolve().parents[1]
PROBE = 0xF040
PHASE = PROBE + 4
WAIT_SEED = 0x91
WAIT_ZOMBIE = 0x92
RECORD_SIZE = 43
HANDLER_ADDRESS = 0xC900


def wait_symbols(path: Path) -> dict[str, int]:
    names = (
        "state", "operation", "sequence", "descriptor", "count", "flags",
        "selector", "selector_high", "child", "status",
    )
    text = path.read_text(encoding="utf-8")
    found: dict[str, int] = {}
    for name in names:
        symbol = f"_udeks_task_wait_{name}_private"
        match = re.search(
            rf"{re.escape(symbol)}\s+([0-9A-Fa-f]{{6}})\s+RL[AZ]", text
        )
        if match is None:
            raise ValueError(f"scheduler map lacks {symbol}")
        found[name] = int(match.group(1), 16)
    return found


def seed_targets(
    port: int, slots: int, waits: dict[str, int], signal: int
) -> None:
    """Install a blocked child and unrelated task in one paused session."""
    child = bytes((1, 4, 3, 1, 0, 0, 0, 0))
    unrelated = bytes((0, 2, 0, 1, 0, 0, 0, 0))
    pending = {
        "state": 1,
        "operation": 0x0D,
        "sequence": 0x55,
        "descriptor": 0,
        "count": 2,
        "flags": 0,
        "selector": 0x34,
        "selector_high": 0x12,
        "child": 0,
        "status": 0,
    }
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
                    raise RuntimeError("VICE monitor closed while seeding CANCEL")
                buffer += chunk

        mcr = parse_monitor_byte(run("m ff00 ff00", b":ff00"), 0xFF00)
        run("> ff01 00")
        for offset, value in enumerate(child):
            run(f"> {slots + 8 + offset:04x} {value:02x}")
        for offset, value in enumerate(unrelated):
            run(f"> {slots + 16 + offset:04x} {value:02x}")
        for name, value in pending.items():
            run(f"> {waits[name] + 1:04x} {value:02x}")
        run(f"> ff00 {mcr:02x}")
        run(f"> {PHASE:04x} {signal:02x}")
        connection.sendall(b"x\n")


def release(port: int, signal: int) -> None:
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
                    raise RuntimeError("VICE monitor closed while releasing CANCEL")
                buffer += chunk

        mcr = parse_monitor_byte(run("m ff00 ff00", b":ff00"), 0xFF00)
        run("> ff01 00")
        run(f"> {PHASE:04x} {signal:02x}")
        run(f"> ff00 {mcr:02x}")
        connection.sendall(b"x\n")


def run(
    disk: Path, overlay_map: Path, handler_path: Path,
    timeout: float, flatpak_id: str,
) -> None:
    symbols = scheduler_symbols(overlay_map)
    waits = wait_symbols(overlay_map)
    slots = symbols["_udeks_lifecycle_slots_private"]
    last_event = symbols["_udeks_lifecycle_last_event_private"]
    handler = handler_path.read_bytes()
    port = choose_port()
    deadline = time.monotonic() + timeout
    process, master_fd = sp.launch_vice(disk.resolve(), port, flatpak_id)
    work = ROOT / "build/vice"
    work.mkdir(parents=True, exist_ok=True)
    try:
        print(f"{disk.name}: booting CANCEL parent", flush=True)
        sp.wait_for_byte(port, PHASE, WAIT_SEED, deadline)
        seed_targets(port, slots, waits, 0xA6)
        sp.wait_for_byte(port, PHASE, WAIT_ZOMBIE, deadline)

        blocks = [
            (work / "task-cancel-mid-record.bin", PROBE, PROBE + RECORD_SIZE - 1, "kernel"),
            (work / "task-cancel-zombie.bin", slots + 8, slots + 15, "kernel"),
            (work / "task-cancel-event.bin", last_event, last_event, "kernel"),
        ]
        for name, address in waits.items():
            blocks.append(
                (work / f"task-cancel-wait-{name}.bin", address + 1, address + 1, "kernel")
            )
        captured = sp.capture_blocks(port, blocks)
        mid_record, child, event, *pending = captured
        if child[1:7] != bytes((6, 0, 1, 130, 0, 0)):
            raise RuntimeError(
                f"cancelled child slot is {child.hex()}, record {mid_record.hex()}"
            )
        if event != bytes((11,)):
            raise RuntimeError(f"last lifecycle event is {event.hex()}")
        if any(value != b"\x00" for value in pending):
            raise RuntimeError("cancelled child retained a private wait snapshot")

        release(port, 3)
        sp.wait_for_byte(port, PHASE, 0xA5, deadline)
        record, lifecycle, installed = sp.capture_blocks(
            port,
            [
                (work / "task-cancel-record.bin", PROBE, PROBE + RECORD_SIZE - 1, "kernel"),
                (work / "task-cancel-lifecycle.bin", slots, slots + 23, "kernel"),
                (
                    work / "task-cancel-handler.bin",
                    HANDLER_ADDRESS,
                    HANDLER_ADDRESS + len(handler) - 1,
                    "kernel",
                ),
            ],
        )
        if record[:5] != b"UCN0\xA5":
            raise RuntimeError(f"CANCEL record incomplete: {record[:5]!r}")
        if record[5:8] != bytes((0x80, 22, 0x71)):
            raise RuntimeError(f"target-zero response is {record[5:8].hex()}")
        if record[8:11] != bytes((0x80, 22, 0x72)):
            raise RuntimeError(f"self response is {record[8:11].hex()}")
        if record[11:14] != bytes((0x80, 3, 0x73)):
            raise RuntimeError(f"free-target response is {record[11:14].hex()}")
        if record[15:18] != bytes((0x80, 3, 0x74)):
            raise RuntimeError(f"unrelated-target response is {record[15:18].hex()}")
        if record[18:22] != bytes((2, 0, 0, 0x75)):
            raise RuntimeError(f"successful CANCEL response is {record[18:22].hex()}")
        if record[22:25] != bytes((0x80, 3, 0x76)):
            raise RuntimeError(f"zombie-target response is {record[22:25].hex()}")
        if record[25:31] != bytes((2, 1, 0, 0x77, 2, 130)):
            raise RuntimeError(f"WAITPID reap response is {record[25:31].hex()}")
        for offset, target, sequence in (
            (31, 0x0100, 0x78), (34, 0x0101, 0x79),
            (37, 0x0102, 0x7A), (40, 0xFFFF, 0x7B),
        ):
            response = record[offset:offset + 3]
            if response != bytes((0x80, 3, sequence)):
                raise RuntimeError(
                    f"16-bit target ${target:04X} response is {response.hex()}"
                )
        if lifecycle[8:16] != bytes(8):
            raise RuntimeError("WAITPID did not clear the cancelled child slot")
        if lifecycle[16:18] != bytes((0, 2)):
            raise RuntimeError("unrelated runnable task was mutated")
        if installed != handler:
            raise RuntimeError("installed lifecycle handler differs from build")
        print(
            f"{disk.name}: invalid/16-bit/free/unrelated rejected; blocked child -> "
            "ZOMBIE(130), wait snapshot cleared, WAITPID reaped",
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
        default=ROOT / "build/boot/udeks-task-cancel-probe.d71",
    )
    parser.add_argument(
        "--map", type=Path,
        default=ROOT / "build/8502/udeks-scheduler-overlay.map",
    )
    parser.add_argument(
        "--handler", type=Path,
        default=ROOT / "build/8502/task-yield-handler.bin",
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    try:
        run(args.disk, args.map, args.handler, args.timeout, args.flatpak_id)
    except (KeyError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"task-CANCEL probe failed: {error}") from error
    print("task-CANCEL probe OK")


if __name__ == "__main__":
    main()

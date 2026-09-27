#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prove that a successful production EXIT cannot resume its caller."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shadow_boot_probe as sp
from vice_capture import choose_port


ROOT = Path(__file__).resolve().parents[1]
TASK_STATE_OFFSET = 1
TASK_EXIT_OFFSET = 4
TASK_ZOMBIE = 6
EXIT_STATUS = 37
TREQ_IDLE = 0
OP_EXIT = 11
HANDLER_ADDRESS = 0xCB00


def scheduler_symbols(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    return {
        name: int(address, 16)
        for name, address in re.findall(
            r"(_udeks_lifecycle_(?:slots|current)_private)\s+"
            r"([0-9A-Fa-f]{6})\s+RL[AZ]",
            text,
        )
    }


def probe_disk(
    disk: Path, map_path: Path, handler_path: Path, flatpak_id: str,
) -> None:
    symbols = scheduler_symbols(map_path)
    slots = symbols["_udeks_lifecycle_slots_private"]
    current = symbols["_udeks_lifecycle_current_private"]
    if current != slots + 64:
        raise RuntimeError(
            "lifecycle current byte does not immediately follow the 64-byte slot table"
        )
    handler = handler_path.read_bytes()
    port = choose_port()
    process, master_fd = sp.launch_vice(disk.resolve(), port, flatpak_id)
    try:
        print(f"{disk.name}: booting EXIT task", flush=True)
        time.sleep(6.0)
        if process.poll() is not None:
            raise RuntimeError(f"VICE exited during boot with status {process.returncode}")
        print(f"{disk.name}: VICE running; capturing EXIT state", flush=True)
        work = ROOT / "build/vice"
        work.mkdir(parents=True, exist_ok=True)
        state, request, tail, installed = sp.capture_blocks(
            port,
            [
                (work / "task-exit-state.bin", slots, current, "kernel"),
                (work / "task-exit-request.bin", 0xF359, 0xF366, "kernel"),
                (work / "task-exit-tail.bin", 0xFF05, 0xFF0E, "kernel"),
                (
                    work / "task-exit-handler.bin",
                    HANDLER_ADDRESS,
                    HANDLER_ADDRESS + len(handler) - 1,
                    "kernel",
                ),
            ],
        )
        if state[TASK_STATE_OFFSET] != TASK_ZOMBIE:
            raise RuntimeError(
                "EXIT task did not become a zombie: "
                f"state={state[TASK_STATE_OFFSET]:02x}, "
                f"current={state[-1]:02x}, request={request[6]:02x}/"
                f"{request[7]:02x}/{request[12]:02x}"
            )
        if tail[:4] != b"UTG2":
            raise RuntimeError(f"task tail signature is {tail[:4]!r}")
        if installed != handler:
            raise RuntimeError("installed lifecycle handler differs from linked image")
        if state[TASK_EXIT_OFFSET] != EXIT_STATUS:
            raise RuntimeError("zombie does not retain exit status 37")
        if state[-1] != 0:
            raise RuntimeError("EXIT left a lifecycle task marked current")
        if request[6] != TREQ_IDLE:
            raise RuntimeError("EXIT did not release the shared request record")
        if request[7] != OP_EXIT:
            raise RuntimeError("EXIT request operation was corrupted")
        if request[11] != 0 or request[12] != 0:
            raise RuntimeError("EXIT returned to its dead caller or published an error")

        first = int.from_bytes(tail[8:10], "little")
        if first == 0:
            raise RuntimeError("EXIT did not suspend through the common task gate")
        time.sleep(0.75)
        second_tail = sp.capture_blocks(
            port,
            [(work / "task-exit-tail-after.bin", 0xFF05, 0xFF0E, "kernel")],
        )[0]
        second = int.from_bytes(second_tail[8:10], "little")
        if second != first:
            raise RuntimeError("exited task resumed and submitted another request")
        print(
            f"{disk.name}: zombie status={EXIT_STATUS}, suspensions stable at {first}",
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
        default=ROOT / "build/boot/udeks-task-exit-probe.d71",
    )
    parser.add_argument(
        "--map", type=Path,
        default=ROOT / "build/8502/udeks-scheduler-overlay.map",
    )
    parser.add_argument(
        "--handler", type=Path,
        default=ROOT / "build/8502/task-yield-handler.bin",
    )
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    try:
        probe_disk(args.disk, args.map, args.handler, args.flatpak_id)
    except (KeyError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"task-EXIT probe failed: {error}") from error
    print("task-EXIT probe OK")


if __name__ == "__main__":
    main()

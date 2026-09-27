#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the first production cooperative YIELD path under VICE."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shadow_boot_probe as sp
from capability_relocation_probe import inject_until_state
from vice_capture import choose_port, monitor_command, parse_monitor_byte


ROOT = Path(__file__).resolve().parents[1]
UTSK_BASE = 0xF110
UTSK_STATE = UTSK_BASE + 6
UTSK_CURRENT = UTSK_BASE + 7
UTSK_RUNNABLE = UTSK_BASE + 8
UTSK_SWITCHES_LOW = UTSK_BASE + 12
UTSK_SWITCHES_HIGH = UTSK_BASE + 13
UTSK_READY = 1
TREQ_STATE = 0xF35F
TREQ_ERROR = 0xF365
TAIL_SIGNATURE = 0xFF05
TAIL_SWITCHES_LOW = 0xFF0D
TAIL_SWITCHES_HIGH = 0xFF0E
def byte(port: int, address: int) -> int:
    return parse_monitor_byte(
        monitor_command(port, f"m {address:04x} {address:04x}"), address
    )


def word(port: int, low_address: int) -> int:
    return byte(port, low_address) | (byte(port, low_address + 1) << 8)


def wait_for_switches(port: int, minimum: int, deadline: float) -> int:
    while time.monotonic() < deadline:
        switches = word(port, TAIL_SWITCHES_LOW)
        if switches >= minimum:
            return switches
        time.sleep(0.2)
    raise TimeoutError(f"task switch count did not reach {minimum}")


def probe_disk(
    disk: Path, map_path: Path, timeout: float, flatpak_id: str,
) -> None:
    symbols = sp.symbol_addresses(map_path)
    port = choose_port()
    process, master_fd = sp.launch_vice(disk.resolve(), port, flatpak_id)
    try:
        print(f"{disk.name}: booting", flush=True)
        time.sleep(6.0)
        deadline = time.monotonic() + timeout
        sp.wait_for_byte(port, sp.ROOT_TERMINAL_STATUS_READY_ADDRESS,
                         sp.ROOT_TERMINAL_STATUS_READY, deadline)
        sp.wait_for_byte(port, UTSK_STATE, UTSK_READY, deadline)
        signature = bytes(byte(port, TAIL_SIGNATURE + index) for index in range(4))
        if signature != b"UTG2":
            page_path = ROOT / "build/vice/task-yield-page.bin"
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page = sp.capture_blocks(
                port, [(page_path, 0x1C00, 0x1FFF, "kernel")]
            )[0]
            gate = page[0x1E:0x2B]
            source_path = ROOT / "build/vice/task-yield-tail-source.bin"
            live_path = ROOT / "build/vice/task-yield-tail-live.bin"
            source, live = sp.capture_blocks(
                port,
                [
                    (source_path, 0x6151, 0x6210, "worker"),
                    (live_path, 0xFF05, 0xFFC4, "kernel"),
                ],
            )
            raise RuntimeError(
                f"task tail signature is {signature!r}; "
                f"UTSK={byte(port, UTSK_STATE):02x}/"
                f"{byte(port, UTSK_CURRENT):02x}/"
                f"{byte(port, UTSK_RUNNABLE):02x}, gate={gate.hex()}, "
                f"source={source[:6]!r}, live={live[:6]!r}"
            )
        initial_request_state = byte(port, TREQ_STATE)
        initial_request_operation = byte(port, TREQ_STATE + 1)
        initial_request_error = byte(port, TREQ_ERROR)
        print(
            f"{disk.name}: tail active, suspensions={word(port, TAIL_SWITCHES_LOW)}, "
            f"request={initial_request_state:02x}/"
            f"{initial_request_operation:02x}/"
            f"{initial_request_error:02x}, "
            f"service={byte(port, 0xF095):02x}/"
            f"{byte(port, 0xF096):02x}/"
            f"{byte(port, 0xF0A5):02x}/"
            f"{byte(port, 0xF0A6):02x}, "
            f"panic={byte(port, 0xF0B5):02x}/"
            f"{byte(port, 0xF0B6):02x}",
            flush=True,
        )
        first = wait_for_switches(port, 2, deadline)
        time.sleep(0.5)
        second = wait_for_switches(port, first + 1, deadline)
        if byte(port, UTSK_CURRENT) not in (0, 1):
            raise RuntimeError("invalid current-task id")
        if byte(port, UTSK_RUNNABLE) > 1:
            raise RuntimeError("single-task runnable count exceeds one")
        inject_until_state(
            port,
            symbols,
            "xinit",
            sp.VIC_STATUS_STATE_ADDRESS,
            sp.VIC_STATUS_ACTIVE,
            deadline,
        )
        print(f"{disk.name}: xinit active", flush=True)
        inject_until_state(
            port,
            symbols,
            "xclock &",
            sp.XCLOCK_STATUS_STATE_ADDRESS,
            sp.XCLOCK_STATUS_RUNNING,
            deadline,
        )
        print(f"{disk.name}: xclock active", flush=True)
        third = wait_for_switches(port, second + 1, deadline)
        print(
            f"{disk.name}: {first}->{second}->{third} cooperative suspensions, "
            "xinit/xclock accepted",
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
    parser.add_argument("--disk", type=Path, default=ROOT / "build/boot/udeks.d71")
    parser.add_argument("--map", type=Path, default=ROOT / "build/8502/udeks-8502.map")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    try:
        probe_disk(
            args.disk, args.map, args.timeout, args.flatpak_id
        )
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"task-YIELD probe failed: {error}") from error
    print("task-YIELD probe OK")


if __name__ == "__main__":
    main()

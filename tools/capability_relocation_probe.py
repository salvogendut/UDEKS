#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the relocated boot-only capability service under VICE.

Both disk formats must produce the same valid HCAP record and must contain an
exact copy of the linked service in application slot 1 during service startup.
The D71 run additionally starts xclock, proving slot 1 is reused, then calls
``udeks_service_start_all`` again through a dead boot-page trampoline.  The
idempotent call must return zero without changing one byte of the live app.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shadow_boot_probe as sp
from capability_decode import parse_result as parse_capability
from gen_capability_imports import map_exports
from vice_capture import choose_port, monitor_command, receive_prompts


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_ADDRESS = 0x0200
CAPABILITY_BSS_SIZE = 1
CAPABILITY_STATE = 0xF0C5
CAPABILITY_READY = 2
TRAMPOLINE_ADDRESS = 0x0B00
TRAMPOLINE_RESULT = 0x0B20
TRAMPOLINE_DONE = 0x0B21
TRAMPOLINE_MARKER = 0xA5


def install_and_resume(port: int, address: int, payload: bytes) -> None:
    """Install a bank-0 trampoline and enter it in one paused session."""
    with socket.create_connection(("127.0.0.1", port), timeout=3.0) as connection:
        connection.settimeout(3.0)
        # A monitor connection does not reliably emit its initial prompt until
        # it receives a command. A marked read synchronizes that prompt and
        # the command-completion prompt before the non-returning goto.
        connection.sendall(b"m ff00 ff00\n")
        reply = receive_prompts(connection, 2)
        if b":ff00" not in reply.lower():
            raise RuntimeError("VICE monitor did not synchronize before goto")
        # Select the kernel-flat profile and write the trampoline without
        # resuming between commands.  The old two-session sequence raced the
        # running managed app: it could switch banks after the monitor write
        # and before goto, leaving $0B00 absent from the active bank.
        connection.sendall(b"> ff01 00\n")
        receive_prompts(connection, 1)
        values = " ".join(f"{byte:02x}" for byte in payload)
        connection.sendall(f"> {address:04x} {values}\n".encode("ascii"))
        receive_prompts(connection, 1)
        connection.sendall(f"goto {address:04x}\n".encode("ascii"))


def call_start_again(port: int, entry: int, deadline: float) -> None:
    # SEI; select the kernel-flat MMU profile; JSR entry; STA result;
    # LDA #marker; STA done; JMP self. The explicit profile is essential: a
    # debugger may have interrupted a managed app while another profile was
    # selected, whereas the real service boundary always runs kernel-flat.
    code = bytes(
        (
            0x78,
            0xA9, 0x00,
            0x8D, 0x01, 0xFF,
            0x20, entry & 0xFF, entry >> 8,
            0x8D, TRAMPOLINE_RESULT & 0xFF, TRAMPOLINE_RESULT >> 8,
            0xA9, TRAMPOLINE_MARKER,
            0x8D, TRAMPOLINE_DONE & 0xFF, TRAMPOLINE_DONE >> 8,
            0x4C, 0x11, 0x0B,
        )
    )
    payload = code.ljust(TRAMPOLINE_RESULT - TRAMPOLINE_ADDRESS, b"\x00")
    payload += b"\xff\x00"
    install_and_resume(port, TRAMPOLINE_ADDRESS, payload)
    sp.wait_for_byte(port, TRAMPOLINE_DONE, TRAMPOLINE_MARKER, deadline)
    sp.wait_for_byte(port, TRAMPOLINE_RESULT, 0, deadline)


def inject_until_state(
    port: int,
    symbols: dict[str, int],
    command: str,
    state_address: int,
    state_value: int,
    deadline: float,
) -> None:
    """Retry line-editor injection until the requested service state wins."""
    while time.monotonic() < deadline:
        sp.inject_line(port, symbols, command)
        try:
            sp.wait_for_byte(
                port,
                state_address,
                state_value,
                min(deadline, time.monotonic() + 6.0),
            )
            return
        except TimeoutError:
            pass
    raise TimeoutError(
        f"${state_address:04X} never reached ${state_value:02X} "
        f"after {command}"
    )


def probe_disk(
    disk: Path,
    capability: bytes,
    map_path: Path,
    work: Path,
    exercise_reentry: bool,
    timeout: float,
    flatpak_id: str,
) -> bytes:
    exports = map_exports(map_path.read_text(encoding="utf-8"))
    try:
        start_all = exports["_udeks_service_start_all"][0]
    except KeyError as error:
        raise ValueError("service-start export is missing from the map") from error
    symbols = sp.symbol_addresses(map_path)
    port = choose_port()
    process, master_fd = sp.launch_vice(disk.resolve(), port, flatpak_id)
    try:
        print(f"{disk.name}: booting", flush=True)
        time.sleep(6.0)
        deadline = time.monotonic() + timeout
        sp.wait_for_byte(port, CAPABILITY_STATE, CAPABILITY_READY, deadline)
        print(f"{disk.name}: HCAP ready", flush=True)
        record_path = work / f"{disk.suffix[1:]}-capability.bin"
        slot_path = work / f"{disk.suffix[1:]}-slot1-at-start.bin"
        record, slot = sp.capture_blocks(
            port,
            [
                (record_path, 0xF0C0, 0xF0DF, "kernel"),
                (
                    slot_path,
                    CAPABILITY_ADDRESS,
                    CAPABILITY_ADDRESS + len(capability),
                    "kernel",
                ),
            ],
        )
        # capture_blocks returns headerless bytes while VICE's on-disk save
        # retains its two-byte load address. Evidence files are raw records.
        record_path.write_bytes(record)
        slot_path.write_bytes(slot)
        parse_capability(record)
        if slot != capability + bytes(CAPABILITY_BSS_SIZE):
            raise RuntimeError(
                f"{disk.name}: slot 1 is not the linked capability image"
            )
        print(f"{disk.name}: slot 1 image matches", flush=True)

        if exercise_reentry:
            sp.wait_for_byte(
                port,
                sp.ROOT_TERMINAL_STATUS_READY_ADDRESS,
                sp.ROOT_TERMINAL_STATUS_READY,
                deadline,
            )
            xinit_deadline = time.monotonic() + timeout
            inject_until_state(
                port, symbols, "xinit", sp.VIC_STATUS_STATE_ADDRESS,
                sp.VIC_STATUS_ACTIVE, xinit_deadline,
            )
            print(f"{disk.name}: xinit active", flush=True)
            xclock_deadline = time.monotonic() + timeout
            inject_until_state(
                port, symbols, "xclock", sp.XCLOCK_STATUS_STATE_ADDRESS,
                sp.XCLOCK_STATUS_RUNNING, xclock_deadline,
            )
            print(f"{disk.name}: xclock running", flush=True)
            before_path = work / "d71-slot1-before-reentry.bin"
            after_path = work / "d71-slot1-after-reentry.bin"
            before = sp.capture_blocks(
                port,
                [
                    (
                        before_path,
                        CAPABILITY_ADDRESS,
                        CAPABILITY_ADDRESS + len(capability),
                        "kernel",
                    )
                ],
            )[0]
            before_path.write_bytes(before)
            print(f"{disk.name}: captured live slot 1", flush=True)
            if before == capability + bytes(CAPABILITY_BSS_SIZE):
                raise RuntimeError("xclock did not overwrite capability slot 1")
            print(f"{disk.name}: invoking service-start re-entry", flush=True)
            call_start_again(port, start_all, time.monotonic() + timeout)
            print(f"{disk.name}: service-start re-entry returned", flush=True)
            after = sp.capture_blocks(
                port,
                [
                    (
                        after_path,
                        CAPABILITY_ADDRESS,
                        CAPABILITY_ADDRESS + len(capability),
                        "kernel",
                    )
                ],
            )[0]
            after_path.write_bytes(after)
            if after != before:
                raise RuntimeError("service-start re-entry changed the live xclock image")
        return record
    finally:
        sp.terminate(process, port)
        try:
            os.close(master_fd)
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d71", type=Path, default=ROOT / "build/boot/udeks.d71")
    parser.add_argument("--d64", type=Path, default=ROOT / "build/boot/udeks.d64")
    parser.add_argument(
        "--capability", type=Path,
        default=ROOT / "build/boot/8502-capability.bin",
    )
    parser.add_argument("--map", type=Path, default=ROOT / "build/8502/udeks-8502.map")
    parser.add_argument("--work", type=Path, default=ROOT / "build/vice/capability")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    capability = args.capability.read_bytes()
    try:
        d71 = probe_disk(
            args.d71, capability, args.map, args.work, True,
            args.timeout, args.flatpak_id,
        )
        d64 = probe_disk(
            args.d64, capability, args.map, args.work, False,
            args.timeout, args.flatpak_id,
        )
        if d71 != d64:
            raise RuntimeError("D71 and D64 capability records differ")
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"capability relocation probe failed: {error}") from error
    print("capability relocation probe OK: D71/D64 records match; re-entry is inert")


if __name__ == "__main__":
    main()

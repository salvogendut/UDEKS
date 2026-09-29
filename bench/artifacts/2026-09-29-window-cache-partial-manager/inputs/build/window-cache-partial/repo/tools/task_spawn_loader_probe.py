#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the load-only SPAWN seam against a native VICE boot."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shadow_boot_probe as sp
from vice_capture import choose_port


ROOT = Path(__file__).resolve().parents[1]
CALLER = 0x0C00
RESULT = 0x0C20
NAME = 0x0C30
TASK_STATUS = 0xF280
TASK_HEADER = TASK_STATUS + 16
SPAWN_LOADER = 0xF919
BOOTFS_BASE = 0xA000


def bootfs_udex_address(bootfs: bytes, name: bytes, executable: bytes) -> int:
    if len(bootfs) < 16 or bootfs[:4] != b"UBFS" or bootfs[7] != 24:
        raise ValueError("probe bootfs has an invalid header")
    for index in range(bootfs[6]):
        entry = 16 + index * 24
        name_length = bootfs[entry + 1]
        if bootfs[entry + 8 : entry + 8 + name_length] != name:
            continue
        offset = int.from_bytes(bootfs[entry + 2 : entry + 4], "little")
        size = int.from_bytes(bootfs[entry + 4 : entry + 6], "little")
        if bootfs[offset : offset + size] != executable:
            raise ValueError("probe executable differs from its bootfs entry")
        return BOOTFS_BASE + offset
    raise ValueError("probe executable is absent from the bootfs image")


def install_and_enter(
    port: int, name: bytes, udex_address: int, image_size: int, bss_size: int
) -> None:
    if not 1 <= len(name) <= 16 or b"\x00" in name:
        raise ValueError("probe name must contain 1..16 nonzero bytes")
    caller = bytes((
        0xA9, NAME & 0xFF,             # LDA #<name
        0xA2, NAME >> 8,               # LDX #>name
        0x20, SPAWN_LOADER & 0xFF, SPAWN_LOADER >> 8,  # JSR loader
        0x8D, RESULT + 1 & 0xFF, RESULT >> 8,          # STA result+1
        0x8E, RESULT + 2 & 0xFF, RESULT >> 8,          # STX result+2
        0xA9, 0xA5,                    # LDA #$A5
        0x8D, RESULT & 0xFF, RESULT >> 8,              # STA result
        0x4C, 0x12, 0x0C,              # JMP $0C12
    ))
    with socket.create_connection(("127.0.0.1", port), timeout=3.0) as connection:
        connection.settimeout(15.0)
        buffer = b""

        def run(command: str, marker: bytes | None = None) -> None:
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
                    return
                chunk = connection.recv(4096)
                if not chunk:
                    raise RuntimeError("VICE monitor closed during SPAWN load setup")
                buffer += chunk

        run("m ff00 ff00", b":ff00")
        run("> ff01 00")
        run(f"> {CALLER:04x} {caller.hex(' ')}")
        run(f"> {RESULT:04x} 00 00 00")
        run(f"> {NAME:04x} {(name + bytes(1)).hex(' ')}")
        if bss_size:
            # Exercise the real BSS path: alter only the live UDEX header and
            # seed the destination under the worker profile with nonzero data.
            run("> ff04 00")
            run(
                f"> {udex_address + 12:04x} "
                f"{bss_size & 0xff:02x} {bss_size >> 8:02x}"
            )
            bss_address = 0x0200 + image_size
            run(f"> {bss_address:04x} {(bytes([0xa5]) * bss_size).hex(' ')}")
            run("> ff01 00")
        connection.sendall(f"goto {CALLER:04x}\n".encode("ascii"))


def probe(args: argparse.Namespace) -> None:
    disk = args.disk.resolve()
    executable = args.executable.read_bytes()
    if len(executable) < 16 or executable[:4] != b"UDEX":
        raise ValueError("probe executable is not UDEX")
    header = bytearray(executable[:16])
    image_size = int.from_bytes(header[10:12], "little")
    bss_size = args.bss_size
    if not 0 <= bss_size <= 0xFFFF:
        raise ValueError("probe BSS size is outside the UDEX field")
    if image_size + bss_size > 0x0A00:
        raise ValueError("probe image and BSS exceed bank-1 APP1")
    header[12:14] = bss_size.to_bytes(2, "little")
    if header[7] != 0 or int.from_bytes(header[8:10], "little") != 0x0200:
        raise ValueError("probe executable is not an ordinary APP1 UDEX")
    if len(executable) != 16 + image_size:
        raise ValueError("probe executable length disagrees with its header")
    name = args.name.encode("ascii")
    udex_address = bootfs_udex_address(args.bootfs.read_bytes(), name, executable)

    port = choose_port()
    process, master_fd = sp.launch_vice(disk, port, args.flatpak_id)
    try:
        deadline = time.monotonic() + args.timeout
        sp.wait_for_byte(
            port,
            sp.ROOT_TERMINAL_STATUS_READY_ADDRESS,
            sp.ROOT_TERMINAL_STATUS_READY,
            deadline,
        )
        work = ROOT / "build/vice"
        work.mkdir(parents=True, exist_ok=True)
        installed = sp.capture_blocks(
            port,
            [(
                work / "task-spawn-loader.bin",
                0xF910,
                0xFEFF,
                "kernel",
            )],
        )[0]
        expected_loader = args.loader.read_bytes()
        if installed[:12] != expected_loader[:12]:
            raise RuntimeError("installed common loader entry vectors differ")
        install_and_enter(port, name, udex_address, image_size, bss_size)
        sp.wait_for_byte(port, RESULT, 0xA5, deadline)
        result, status, loaded = sp.capture_blocks(
            port,
            [
                (work / "task-spawn-loader-result.bin", RESULT, RESULT + 2, "kernel"),
                (work / "task-spawn-loader-status.bin", TASK_STATUS, TASK_HEADER + 15, "kernel"),
                (
                    work / "task-spawn-loader-image.bin",
                    0x0200,
                    0x0200 + image_size + bss_size - 1,
                    "worker",
                ),
            ],
        )
        if result != b"\xA5\x00\x00":
            raise RuntimeError(f"SPAWN loader returned {result.hex()}")
        if status[5:7] != b"\x00\x00" or status[16:32] != bytes(header):
            raise RuntimeError("SPAWN loader status/header record is invalid")
        if loaded[:image_size] != executable[16:]:
            raise RuntimeError("bank-1 APP1 image differs from the UDEX payload")
        if loaded[image_size:] != bytes(bss_size):
            raise RuntimeError("bank-1 APP1 BSS was not cleared")
        print(
            f"{disk.name}: {args.name} loaded at bank-1 $0200 "
            f"({image_size} image + {bss_size} BSS bytes) without entry",
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
    parser.add_argument(
        "--executable", type=Path, default=ROOT / "build/user/cowsay.udx"
    )
    parser.add_argument(
        "--loader", type=Path, default=ROOT / "build/boot/task-loader.bin"
    )
    parser.add_argument(
        "--bootfs", type=Path, default=ROOT / "build/user/bootfs.img"
    )
    parser.add_argument(
        "--bss-size", type=lambda value: int(value, 0), default=32
    )
    parser.add_argument("--name", default="cowsay")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    try:
        probe(args)
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"task-SPAWN loader probe failed: {error}") from error
    print("task-SPAWN loader probe OK")


if __name__ == "__main__":
    main()

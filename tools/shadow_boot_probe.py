#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the VIC shadow clear and the reclaimed tail in a native VICE boot.

The probe copies the native D71, seeds the staged shadow's newly reclaimed
prefix below the live probe and crt0 staging and the tail sentinels
($CECB/$CEFF) with a nonzero pattern, and boots the copy.  Because the seed
travels with the payload, both stage 1 and crt0 run after it is planted.
Seeding the prefix that the staged image leaves zero means a clear that starts
late cannot pass; the $AD00-$ADFF probe and $AE00-$AEFF crt0 staging are live
and must not be seeded.  After boot the probe saves the same
window and checks that crt0 cleared every VICSHADOW byte through
__VICSHADOW_RUN__/__VICSHADOW_SIZE__ while the complete reclaimed tail still
matches the preserved preimage byte for byte.

With --vic-compare it injects xinit and xclock, saves the drawn bank-0 shadow
and the bank-1 $6000-$7F3F bitmap through a worker-bank MMU switch, and
compares them byte for byte.  Every VICE session is terminated on exit.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pty
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_d71 import (
    BOOTFS_TAIL_STAGING_ADDRESS,
    CRT0_SIZE,
    CRT0_STAGING_ADDRESS,
    PAYLOAD_BLOCKS,
    PROBE_SIZE,
    PROBE_STAGING_ADDRESS,
    boot_locations,
    sector_offset,
)
from placement_audit import VIC_SHADOW_SEGMENT, parse_map, vic_bitmap_size
from vice_capture import choose_port, monitor_command, parse_monitor_byte

ROOT = Path(__file__).resolve().parents[1]

PAYLOAD_BASE = 0x1C00
CONSOLE_STATUS_READY_ADDRESS = 0xF075
CONSOLE_STATUS_READY = 2
ROOT_TERMINAL_STATUS_READY_ADDRESS = 0xF155
ROOT_TERMINAL_STATUS_READY = 2
VIC_STATUS_STATE_ADDRESS = 0xF1B5
VIC_STATUS_ACTIVE = 3
XCLOCK_STATUS_STATE_ADDRESS = 0xF225
XCLOCK_STATUS_RUNNING = 3
SYSCALL_PAGE = 0xCF00

# Free tail bytes above the staging payloads defined in tools/build_d71.py:
# the task loader ends at $CDEF and the bank-1 task gate ends at $CECA.
SENTINEL_ADDRESSES = ((0xCECB, 0x5A), (0xCEFF, 0xA5))

LINE_EDITOR_TEXT_SYMBOL = "_udeks_line_editor_submitted_text"
LINE_EDITOR_LENGTH_SYMBOL = "_udeks_line_editor_submitted_length_value"
LINE_EDITOR_READY_SYMBOL = "_udeks_line_editor_submitted_ready_value"
LINE_EDITOR_CURSOR_SYMBOL = "_udeks_line_editor_submitted_cursor"

PROMPT_RE = re.compile(rb"\([A-Za-z0-9]+:\$[0-9a-fA-F]+\) $")


def shadow_bounds(map_path: Path) -> tuple[int, int]:
    _, segments = parse_map(map_path.read_text(encoding="utf-8"))
    for name, start, end in segments:
        if name == VIC_SHADOW_SEGMENT:
            return start, end - start + 1
    raise ValueError(f"{VIC_SHADOW_SEGMENT} segment is missing from the map")


def symbol_addresses(map_path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    wanted = {
        LINE_EDITOR_TEXT_SYMBOL,
        LINE_EDITOR_LENGTH_SYMBOL,
        LINE_EDITOR_READY_SYMBOL,
        LINE_EDITOR_CURSOR_SYMBOL,
    }
    pattern = re.compile(r"(\S+)\s+([0-9A-Fa-f]{4,6})\s+R")
    for match in pattern.finditer(map_path.read_text(encoding="utf-8")):
        if match.group(1) in wanted:
            values[match.group(1)] = int(match.group(2), 16)
    missing = wanted - values.keys()
    if missing:
        raise ValueError(f"line-editor symbols missing from the map: {missing}")
    return values


def line_editor_capacity() -> int:
    header = (ROOT / "include/udeks/line_editor.h").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"^#define\s+UDEKS_LINE_EDITOR_CAPACITY\s+(\d+)u?$",
        header,
        re.MULTILINE,
    )
    if match is None:
        raise ValueError("UDEKS_LINE_EDITOR_CAPACITY is missing")
    return int(match.group(1))


def payload_disk_offset(address: int, locations: list[tuple[int, int]]) -> int:
    payload_offset = address - PAYLOAD_BASE
    sector_index, byte_offset = divmod(payload_offset, 256)
    if not 0 <= sector_index < PAYLOAD_BLOCKS:
        raise ValueError(f"${address:04X} is outside the boot payload")
    track, sector = locations[1 + sector_index]
    return sector_offset(track, sector) + byte_offset


def patch_payload(
    d71: Path, target: Path, shadow_start: int, tail_end: int
) -> bytes:
    """Seed safe zero bytes and return the staged $shadow_start-$tail_end image."""
    image = bytearray(d71.read_bytes())
    locations = list(boot_locations(1 + PAYLOAD_BLOCKS))
    if CRT0_STAGING_ADDRESS + CRT0_SIZE > BOOTFS_TAIL_STAGING_ADDRESS:
        raise ValueError("crt0 staging is not below bootfs staging")
    if PROBE_STAGING_ADDRESS + PROBE_SIZE > CRT0_STAGING_ADDRESS:
        raise ValueError("probe staging is not below crt0 staging")
    prefix_end = PROBE_STAGING_ADDRESS - 1
    for offset, address in enumerate(range(shadow_start, prefix_end + 1)):
        disk_offset = payload_disk_offset(address, locations)
        if image[disk_offset] != 0:
            raise ValueError(
                f"shadow prefix ${address:04X} does not overlay a zero byte"
            )
        image[disk_offset] = (offset % 255) + 1
    for address, value in SENTINEL_ADDRESSES:
        disk_offset = payload_disk_offset(address, locations)
        if image[disk_offset] != 0:
            raise ValueError(
                f"sentinel ${address:04X} does not overlay a zero byte"
            )
        image[disk_offset] = value
    target.write_bytes(image)
    preimage = bytes(
        image[payload_disk_offset(address, locations)]
        for address in range(shadow_start, tail_end + 1)
    )
    for name, address, size in (
        ("probe", PROBE_STAGING_ADDRESS, PROBE_SIZE),
        ("crt0", CRT0_STAGING_ADDRESS, CRT0_SIZE),
    ):
        staged = preimage[address - shadow_start : address - shadow_start + size]
        if not any(staged):
            raise ValueError(f"{name} staging is empty in the boot payload")
    return preimage


def capture_blocks(
    port: int, blocks: list[tuple[Path, int, int, str]]
) -> list[bytes]:
    """Save memory blocks with explicit MMU profiles in one paused session.

    The live MMU configuration register is read first and restored before the
    CPU resumes, so forcing the kernel or worker profile cannot corrupt a
    cooperative bank switch in progress.
    """
    with socket.create_connection(("127.0.0.1", port), timeout=3.0) as connection:
        connection.settimeout(15.0)
        buffer = b""

        def run(command: str, marker: bytes | None) -> bytes:
            nonlocal buffer
            start = len(buffer)
            connection.sendall(command.encode("ascii") + b"\n")
            while True:
                fresh = buffer[start:]
                if (
                    fresh.endswith(b") ")
                    and PROMPT_RE.search(fresh[-32:])
                    and (marker is None or marker in fresh)
                ):
                    return fresh
                chunk = connection.recv(4096)
                if not chunk:
                    raise RuntimeError("VICE monitor closed mid-session")
                buffer += chunk

        mcr = parse_monitor_byte(run("m ff00 ff00", b":ff00"), 0xFF00)
        saved: list[bytes] = []
        for path, start, end, profile in blocks:
            path.unlink(missing_ok=True)
            selector = 0x01 if profile == "kernel" else 0x04
            run(f"> ff{selector:02x} 00", None)
            reply = run(
                f'save "{path.resolve()}" 0 {start:04x} {end:04x}',
                b"Saving file",
            )
            if b"Saving file" not in reply:
                raise RuntimeError(f"VICE refused to save ${start:04X}")
            saved.append(path.read_bytes()[2:])
        run(f"> ff00 {mcr:02x}", None)
        connection.sendall(b"x\n")
    return saved


def wait_for_byte(port: int, address: int, value: int, deadline: float) -> None:
    while time.monotonic() < deadline:
        try:
            reply = monitor_command(port, f"m {address:04x} {address:04x}")
            if parse_monitor_byte(reply, address) == value:
                return
        except (ConnectionError, OSError, RuntimeError, ValueError):
            pass
        time.sleep(0.2)
    raise TimeoutError(f"${address:04X} never reached ${value:02X}")


def inject_line(port: int, symbols: dict[str, int], text: str) -> None:
    payload = text.encode("ascii")
    if len(payload) > line_editor_capacity():
        raise ValueError("injected line exceeds the line-editor capacity")
    text_address = symbols[LINE_EDITOR_TEXT_SYMBOL]
    length_address = symbols[LINE_EDITOR_LENGTH_SYMBOL]
    if (
        symbols[LINE_EDITOR_READY_SYMBOL] != length_address + 1
        or symbols[LINE_EDITOR_CURSOR_SYMBOL] != length_address + 2
    ):
        raise ValueError("line-editor submitted record layout changed")
    record = bytearray(length_address - text_address + 3)
    record[: len(payload)] = payload
    record[length_address - text_address] = len(payload)
    record[length_address - text_address + 1] = 1
    values = " ".join(f"{byte:02x}" for byte in record)
    monitor_command(port, f"> {text_address:04x} {values}")


def launch_vice(
    d71: Path, port: int, flatpak_id: str
) -> tuple[subprocess.Popen, int]:
    command = [
        "flatpak",
        "run",
        "--share=network",
        "--command=x128",
        flatpak_id,
        "-default",
        "+sound",
        "-warp",
        "-seed",
        "0",
        "-remotemonitor",
        "-remotemonitoraddress",
        f"ip4://127.0.0.1:{port}",
        "-8",
        str(d71),
    ]
    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        command,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        start_new_session=True,
    )
    os.close(slave_fd)

    def drain() -> None:
        try:
            while os.read(master_fd, 4096):
                pass
        except OSError:
            pass

    threading.Thread(target=drain, daemon=True).start()
    return process, master_fd


def terminate(process: subprocess.Popen, port: int) -> None:
    if process.poll() is None:
        try:
            with socket.create_connection(
                ("127.0.0.1", port), timeout=1.0
            ) as connection:
                connection.settimeout(1.0)
                connection.sendall(b"quit\n")
        except (ConnectionError, OSError, RuntimeError):
            pass
    try:
        process.wait(timeout=8.0)
    except subprocess.TimeoutExpired:
        pass
    if process.poll() is None:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
        process.wait()


def probe(args: argparse.Namespace) -> None:
    d71 = args.d71.resolve()
    if not d71.is_file():
        raise SystemExit(f"missing native disk: {d71}")
    shadow_start, shadow_size = shadow_bounds(args.map.resolve())
    if shadow_size != vic_bitmap_size():
        raise SystemExit(
            f"VICSHADOW is {shadow_size} bytes, expected {vic_bitmap_size()}"
        )
    tail_end = SYSCALL_PAGE - 1
    for address, _ in SENTINEL_ADDRESSES:
        if not shadow_start + shadow_size <= address <= tail_end:
            raise SystemExit(
                f"sentinel ${address:04X} is not in the reclaimed tail"
            )
    symbols = symbol_addresses(args.map.resolve())

    args.work.mkdir(parents=True, exist_ok=True)
    probe_disk = args.work / "shadow-probe.d71"
    preimage = patch_payload(d71, probe_disk, shadow_start, tail_end)

    port = choose_port()
    process, master_fd = launch_vice(probe_disk, port, args.flatpak_id)
    try:
        time.sleep(6.0)
        deadline = time.monotonic() + args.timeout
        wait_for_byte(
            port, CONSOLE_STATUS_READY_ADDRESS, CONSOLE_STATUS_READY, deadline
        )
        wait_for_byte(
            port,
            ROOT_TERMINAL_STATUS_READY_ADDRESS,
            ROOT_TERMINAL_STATUS_READY,
            deadline,
        )

        window = capture_blocks(
            port,
            [
                (
                    args.work / "shadow-after-boot.bin",
                    shadow_start,
                    tail_end,
                    "kernel",
                )
            ],
        )[0]
        shadow = window[:shadow_size]
        nonzero = sum(1 for byte in shadow if byte != 0)
        if nonzero:
            raise SystemExit(f"shadow is not cleared: {nonzero} nonzero bytes")
        tail = window[shadow_size:]
        preimage_tail = preimage[shadow_size:]
        if tail != preimage_tail:
            first = next(
                offset
                for offset, (actual, staged) in enumerate(
                    zip(tail, preimage_tail)
                )
                if actual != staged
            )
            raise SystemExit(
                f"reclaimed tail changed at "
                f"${shadow_start + shadow_size + first:04X}: "
                f"${tail[first]:02X} != ${preimage_tail[first]:02X}"
            )
        print(
            f"shadow ${shadow_start:04X}-"
            f"${shadow_start + shadow_size - 1:04X} cleared "
            f"({shadow_size} bytes); reclaimed tail "
            f"${shadow_start + shadow_size:04X}-${tail_end:04X} "
            f"matches its {len(tail)}-byte preimage"
        )
        for path, data in (
            (args.preimage_output, preimage),
            (
                args.hash_output,
                (
                    f"{hashlib.sha256(d71.read_bytes()).hexdigest()}"
                    f"  {d71.name}\n"
                ).encode("ascii"),
            ),
        ):
            if path is None:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        if args.vic_compare:
            vic_deadline = time.monotonic() + args.timeout
            while True:
                inject_line(port, symbols, "xinit")
                try:
                    wait_for_byte(
                        port,
                        VIC_STATUS_STATE_ADDRESS,
                        VIC_STATUS_ACTIVE,
                        min(vic_deadline, time.monotonic() + 6.0),
                    )
                    break
                except TimeoutError:
                    if time.monotonic() >= vic_deadline:
                        raise
            xclock_deadline = time.monotonic() + args.timeout
            while True:
                inject_line(port, symbols, "xclock")
                try:
                    wait_for_byte(
                        port,
                        XCLOCK_STATUS_STATE_ADDRESS,
                        XCLOCK_STATUS_RUNNING,
                        min(xclock_deadline, time.monotonic() + 6.0),
                    )
                    break
                except TimeoutError:
                    if time.monotonic() >= xclock_deadline:
                        raise
            time.sleep(args.draw_delay)

            drawn_path = args.work / "shadow-drawn.bin"
            vic_path = args.work / "vic-bitmap.bin"
            drawn, bitmap = capture_blocks(
                port,
                [
                    (
                        drawn_path,
                        shadow_start,
                        shadow_start + shadow_size - 1,
                        "kernel",
                    ),
                    (vic_path, 0x6000, 0x7F3F, "worker"),
                ],
            )
            if len(drawn) != shadow_size or len(bitmap) != shadow_size:
                raise RuntimeError("VIC comparison blocks have the wrong size")
            if all(byte == 0 for byte in drawn):
                raise SystemExit("xclock did not draw into the shadow")
            mismatches = [
                offset
                for offset, (left, right) in enumerate(zip(drawn, bitmap))
                if left != right
            ]
            if mismatches:
                raise SystemExit(
                    f"bank-0 shadow and bank-1 bitmap differ in "
                    f"{len(mismatches)} bytes, first at ${mismatches[0]:04X}"
                )
            print(
                f"bank-0 shadow matches bank-1 $6000-$7F3F "
                f"({shadow_size} bytes)"
            )
            for path, data in (
                (args.boot_output, window),
                (args.shadow_output, drawn),
                (args.vic_output, bitmap),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    finally:
        terminate(process, port)
        try:
            os.close(master_fd)
        except OSError:
            pass
        probe_disk.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--d71", type=Path, default=ROOT / "build/boot/udeks.d71"
    )
    parser.add_argument(
        "--map", type=Path, default=ROOT / "build/8502/udeks-8502.map"
    )
    parser.add_argument("--work", type=Path, default=ROOT / "build/vice")
    parser.add_argument(
        "--boot-output", type=Path,
        default=ROOT / "build/vice/shadow-window.bin",
    )
    parser.add_argument(
        "--shadow-output", type=Path,
        default=ROOT / "build/vice/shadow-drawn.bin",
    )
    parser.add_argument(
        "--vic-output", type=Path,
        default=ROOT / "build/vice/vic-bitmap.bin",
    )
    parser.add_argument(
        "--preimage-output", type=Path,
        default=ROOT / "build/vice/shadow-preimage.bin",
    )
    parser.add_argument(
        "--hash-output", type=Path,
        default=ROOT / "build/vice/D71.sha256",
    )
    parser.add_argument("--vic-compare", action="store_true")
    parser.add_argument("--draw-delay", type=float, default=8.0)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    try:
        probe(args)
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"shadow probe failed: {error}") from error
    print("shadow probe OK")


if __name__ == "__main__":
    main()

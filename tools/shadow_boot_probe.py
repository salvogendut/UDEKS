#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the VIC shadow clear and scheduler tail in a native VICE boot.

The probe copies the native D71, seeds every safe zero byte in the staged
shadow prefix, and boots the copy.  Because the seed travels with the payload,
both stage 1 and crt0 run after it is planted.  Live staging ranges are kept
intact.  After boot the probe checks that crt0 cleared every VICSHADOW byte,
that the linked scheduler core and lifecycle handler were installed correctly,
and that the remaining unassigned gap before the context binding retains its
boot-payload preimage byte for byte.  The context-binding area is owned runtime
state and is deliberately excluded from the preimage comparison.

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
    BOOT_SECTOR_BASE,
    BOOT_SECTOR_SIZE,
    CRT0_SIZE,
    CRT0_STAGING_ADDRESS,
    PAYLOAD_BLOCKS,
    PROBE_SIZE,
    PROBE_STAGING_ADDRESS,
    SCATTER_MANIFEST_ADDRESS,
    SCATTER_MANIFEST_MAX,
    SCHEDULER_TAIL_INSTALLER_SIZE,
    SCHEDULER_TAIL_INSTALLER_STAGING_ADDRESS,
    boot_locations,
    scheduler_holes,
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


def scheduler_tail_bounds(map_path: Path) -> tuple[int, int, int]:
    _, segments = parse_map(map_path.read_text(encoding="utf-8"))
    by_name = {name: (start, end) for name, start, end in segments}
    if "CODE" not in by_name or "BSS" not in by_name:
        raise ValueError("scheduler overlay map lacks CODE or BSS")
    code_start = by_name["CODE"][0]
    bss_start, bss_end = by_name["BSS"]
    return code_start, bss_start, bss_end


def context_binding_start(map_path: Path) -> int:
    _, segments = parse_map(map_path.read_text(encoding="utf-8"))
    for name, start, _ in segments:
        if name == "CODE":
            return start
    raise ValueError("task context map lacks CODE")


def scheduler_installed_tail(path: Path) -> bytes:
    image = path.read_bytes()
    load = int.from_bytes(image[:2], "little")
    # The secondary envelope may also deliver cache/storage at lower addresses.
    # Locate the header only at its two defined source addresses, not by an
    # unconstrained magic search through code or cached pixels.
    headers = [2 + address - load for address in (0x5000, 0x6000)
               if address >= load and image[2+address-load:8+address-load] == b"USOV\x00\x03"]
    if len(headers) != 1:
        raise ValueError("scheduler payload lacks an unambiguous USOV 0.3 header")
    image = b"\x00\x50" + image[headers[0]:]
    if len(image) < 22:
        raise ValueError("scheduler payload has a truncated header")
    page_size = int.from_bytes(image[10:12], "little")
    tail_size = int.from_bytes(image[14:16], "little")
    start = 2 + 20 + page_size
    end = start + tail_size
    if page_size != 0x0400 or end > len(image):
        raise ValueError("scheduler payload page/tail lengths are invalid")
    return image[start:end]


def preserved_gap_size(
    tail_start: int, installed_size: int, context_start: int, tail_limit: int
) -> int:
    """Validate half-open tail bounds, allowing exact handler/context adjacency."""
    gap_start = tail_start + installed_size
    if not tail_start <= gap_start <= context_start <= tail_limit:
        raise ValueError("preserved scheduler/context gap is outside the tail")
    return context_start - gap_start


def validate_gap_preimage(gap: bytes) -> None:
    """An existing free gap needs test data; an adjacent layout has no gap."""
    if gap and not any(gap):
        raise ValueError("preserved scheduler/context gap has no test data")


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


def manifest_chunks(image: bytes, locations: list[tuple[int, int]]) -> list[tuple[int, int]]:
    offset = payload_disk_offset(SCATTER_MANIFEST_ADDRESS, locations)
    manifest = image[offset : offset + SCATTER_MANIFEST_MAX]
    if manifest[:4] != b"USCT":
        return []
    chunks: list[tuple[int, int]] = []
    for index in range(manifest[4]):
        entry = manifest[7 + 4 * index : 7 + 4 * index + 4]
        source = int.from_bytes(entry[:2], "little")
        length = int.from_bytes(entry[2:], "little")
        chunks.append((source, source + length - 1))
    return chunks


def seed_ranges(
    shadow_start: int,
    shadow_end: int,
    occupied: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Free shadow byte ranges that are not live staging."""
    ranges: list[tuple[int, int]] = []
    for start, end in scheduler_holes(shadow_start, BOOT_SECTOR_BASE):
        start = max(start, shadow_start)
        end = min(end, shadow_end)
        if start > end:
            continue
        cursor = start
        for occupied_start, occupied_end in sorted(occupied):
            if occupied_end < cursor or occupied_start > end:
                continue
            if occupied_start > cursor:
                ranges.append((cursor, min(occupied_start - 1, end)))
            cursor = max(cursor, occupied_end + 1)
        if cursor <= end:
            ranges.append((cursor, end))
    return ranges


def patch_payload(
    d71: Path,
    target: Path,
    shadow_start: int,
    shadow_size: int,
    tail_end: int,
    scheduler_size: int,
    boot_delivery: bytes,
    capability: bytes,
    capability_installer: bytes,
    boot_console: bytes,
    task_activation: bytes,
    preserved_gap_start: int,
    context_start: int,
    task_loader: bytes,
) -> bytes:
    """Seed safe zero bytes and return the staged $shadow_start-$tail_end image."""
    image = bytearray(d71.read_bytes())
    locations = list(boot_locations(1 + PAYLOAD_BLOCKS))
    if CRT0_STAGING_ADDRESS + CRT0_SIZE > BOOTFS_TAIL_STAGING_ADDRESS:
        raise ValueError("crt0 staging is not below bootfs staging")
    if PROBE_STAGING_ADDRESS + PROBE_SIZE > CRT0_STAGING_ADDRESS:
        raise ValueError("probe staging is not below crt0 staging")
    shadow_end = shadow_start + shadow_size - 1
    occupied = [
        (
            shadow_start,
            shadow_start + len(boot_delivery) + len(capability)
            + len(capability_installer)
            + len(boot_console) + len(task_activation) - 1,
        ),
        (
            SCATTER_MANIFEST_ADDRESS,
            SCATTER_MANIFEST_ADDRESS + SCATTER_MANIFEST_MAX - 1,
        ),
        (
            SCHEDULER_TAIL_INSTALLER_STAGING_ADDRESS,
            SCHEDULER_TAIL_INSTALLER_STAGING_ADDRESS
            + SCHEDULER_TAIL_INSTALLER_SIZE - 1,
        ),
    ]
    occupied.extend(manifest_chunks(image, locations))
    for name, address, expected in (
        ("boot delivery", shadow_start, boot_delivery),
        ("capability", shadow_start + len(boot_delivery), capability),
        (
            "capability installer",
            shadow_start + len(boot_delivery) + len(capability),
            capability_installer,
        ),
        (
            "boot console",
            shadow_start + len(boot_delivery) + len(capability)
            + len(capability_installer),
            boot_console,
        ),
        (
            "task activation",
            shadow_start + len(boot_delivery) + len(capability)
            + len(capability_installer) + len(boot_console),
            task_activation,
        ),
    ):
        actual = bytes(
            image[payload_disk_offset(address + offset, locations)]
            for offset in range(len(expected))
        )
        if actual != expected:
            raise ValueError(f"{name} staging differs from its linked image")
    for start, end in seed_ranges(shadow_start, shadow_end, occupied):
        for offset, address in enumerate(range(start, end + 1)):
            disk_offset = payload_disk_offset(address, locations)
            if image[disk_offset] != 0:
                raise ValueError(
                    f"shadow prefix ${address:04X} does not overlay a zero byte"
                )
            image[disk_offset] = (offset % 255) + 1
    # The smaller Storage 0.2 common loader leaves zero padding where the
    # scheduler/context gap used to inherit nonzero loader staging. Seed
    # only the proven unused suffix, never executable bytes or another owner.
    staged_loader = bytes(image[payload_disk_offset(0xc800+i, locations)]
                          for i in range(len(task_loader)))
    if not task_loader or staged_loader != task_loader:
        raise ValueError('task-loader staging differs from linked image')
    for address in range(preserved_gap_start, context_start):
        if 0xc800+len(task_loader) <= address < 0xcdf0:
            offset = payload_disk_offset(address, locations)
            if image[offset] != 0:
                raise ValueError('unused task-loader staging is not zero')
            image[offset] = (address % 255)+1
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
    preserved_gap = preimage[
        preserved_gap_start - shadow_start : context_start - shadow_start
    ]
    validate_gap_preimage(preserved_gap)
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
    write_kernel_blocks(port, [(text_address, bytes(record))])


def write_kernel_blocks(port: int, writes: list[tuple[int, bytes]]) -> None:
    """Atomically mutate bank-0 records, preserving the CPU's live MMU map."""
    for address, data in writes:
        if not data or address < 0 or address + len(data) > 0x10000:
            raise ValueError("monitor write must fit in 64 KiB")
    with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
        connection.settimeout(10)
        buffer = b""

        def run(command: str, marker: bytes | None = None) -> bytes:
            nonlocal buffer
            start = len(buffer)
            connection.sendall(command.encode("ascii") + b"\n")
            while True:
                fresh = buffer[start:]
                if (fresh.endswith(b") ") and PROMPT_RE.search(fresh[-32:])
                        and (marker is None or marker in fresh)):
                    return fresh
                chunk = connection.recv(4096)
                if not chunk:
                    raise RuntimeError("VICE monitor closed during kernel write")
                buffer += chunk

        live = parse_monitor_byte(run("m ff00 ff00", b":ff00"), 0xFF00)
        run("> ff01 00")
        for address, data in writes:
            run(f"> {address:04x} " + data.hex(" "))
        run(f"> ff00 {live:02x}")
        connection.sendall(b"x\n")


def launch_vice(
    d71: Path, port: int, flatpak_id: str, extra_args: tuple[str, ...] = ()
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
        *extra_args,
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
    symbols = symbol_addresses(args.map.resolve())
    overlay_start, overlay_bss, overlay_end = scheduler_tail_bounds(
        args.scheduler_map.resolve()
    )
    overlay_image = args.scheduler_tail.read_bytes()
    installed_tail = scheduler_installed_tail(args.scheduler_payload.resolve())
    context_start = context_binding_start(args.task_context_map.resolve())
    preserved_gap_start = overlay_start + len(installed_tail)
    if overlay_start != shadow_start + shadow_size:
        raise SystemExit("scheduler tail does not begin after VICSHADOW")
    gap_size = preserved_gap_size(
        overlay_start, len(installed_tail), context_start, tail_end + 1
    )
    if len(overlay_image) != overlay_bss - overlay_start:
        raise SystemExit("scheduler tail image and map disagree")

    args.work.mkdir(parents=True, exist_ok=True)
    probe_disk = args.work / "shadow-probe.d71"
    scheduler_size = (
        args.scheduler.stat().st_size if args.scheduler.is_file() else 0
    )
    boot_delivery = args.boot_delivery.read_bytes()
    capability = args.capability.read_bytes()
    capability_installer = args.capability_installer.read_bytes()
    boot_console = args.boot_console.read_bytes()
    task_activation = args.task_activation.read_bytes()
    preimage = patch_payload(
        d71,
        probe_disk,
        shadow_start,
        shadow_size,
        tail_end,
        scheduler_size,
        boot_delivery,
        capability,
        capability_installer,
        boot_console,
        task_activation,
        preserved_gap_start,
        context_start,
        args.task_loader.read_bytes(),
    )

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

        window, scheduler_page, task_gate, lifecycle = capture_blocks(
            port,
            [
                (
                    args.work / "shadow-after-boot.bin",
                    shadow_start,
                    tail_end,
                    "kernel",
                ),
                (args.work / "scheduler-page.bin", 0x1C00, 0x1FFF, "kernel"),
                (args.work / "task-gate.bin", 0xFF05, 0xFFCF, "kernel"),
                (args.work / "lifecycle-status.bin", 0xF110, 0xF11F, "kernel"),
            ],
        )
        expected_page = bytearray(args.scheduler_page.read_bytes())
        context_vectors = args.task_context_vectors.read_bytes()
        if len(expected_page) != 0x0400 or len(context_vectors) != 6:
            raise SystemExit("linked scheduler page/vector sizes are invalid")
        # The task-switch activator installs the two fixed callbacks into the
        # six bytes deliberately left zero at the end of the delivered page.
        expected_page[-6:] = context_vectors
        if scheduler_page != expected_page:
            raise SystemExit("installed scheduler page differs from linked image")
        expected_gate = args.task_switch_tail.read_bytes()
        if (
            len(expected_gate) != 0x00C0
            or task_gate[:6] != expected_gate[:6]
            or task_gate[10:179] != expected_gate[10:179]
        ):
            raise SystemExit("activator did not install the task-switch tail")
        if (
            lifecycle[:7] != b"UTSK\x00\x01\x01"
            or lifecycle[7:10] != b"\x01\x01\x01"
            or lifecycle[12:15] != b"\x01\x00\x03"
            or lifecycle[15] != 0
        ):
            raise SystemExit("persistent shell lifecycle bootstrap is invalid")
        shadow = window[:shadow_size]
        nonzero = sum(1 for byte in shadow if byte != 0)
        if nonzero:
            raise SystemExit(f"shadow is not cleared: {nonzero} nonzero bytes")
        tail = window[shadow_size:]
        preimage_tail = preimage[shadow_size:]
        overlay_runtime_size = overlay_end - overlay_start + 1
        if tail[: len(overlay_image)] != overlay_image:
            raise SystemExit("installed scheduler tail differs from linked image")
        # Core BSS is live scheduler state by the time the shell reaches its
        # prompt, so compare around it.  The lifecycle record check above
        # validates the persistent shell state; this comparison proves the
        # zero-filled placement gap and permanent handler remained exact.
        if (
            tail[overlay_runtime_size : len(installed_tail)]
            != installed_tail[overlay_runtime_size :]
        ):
            raise SystemExit("installed scheduler gap/handler image is invalid")
        preserved_tail = tail[
            len(installed_tail) : context_start - overlay_start
        ]
        preserved_preimage = preimage_tail[
            len(installed_tail) : context_start - overlay_start
        ]
        if preserved_tail != preserved_preimage:
            first = next(
                offset
                for offset, (actual, staged) in enumerate(
                    zip(preserved_tail, preserved_preimage)
                )
                if actual != staged
            )
            raise SystemExit(
                f"reclaimed tail changed at "
                f"${overlay_start + len(installed_tail) + first:04X}: "
                f"${preserved_tail[first]:02X} != "
                f"${preserved_preimage[first]:02X}"
            )
        gap_report = (
            f"${preserved_gap_start:04X}-${context_start - 1:04X} matches its "
            f"{gap_size}-byte preimage"
            if gap_size else
            f"handler/context are adjacent at ${context_start:04X} (no free gap)"
        )
        print(
            f"shadow ${shadow_start:04X}-"
            f"${shadow_start + shadow_size - 1:04X} cleared "
            f"({shadow_size} bytes); reclaimed tail "
            f"${shadow_start + shadow_size:04X}-${tail_end:04X} "
            f"contains the {len(installed_tail)}-byte installed scheduler tail; "
            f"{gap_report}"
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
    parser.add_argument(
        "--scheduler", type=Path,
        default=ROOT / "build/8502/udeks-scheduler.bin",
    )
    parser.add_argument(
        "--scheduler-map", type=Path,
        default=ROOT / "build/8502/udeks-scheduler-overlay.map",
    )
    parser.add_argument(
        "--task-context-map", type=Path,
        default=ROOT / "build/8502/task-context-binding.map",
    )
    parser.add_argument(
        "--scheduler-tail", type=Path,
        default=ROOT / "build/8502/udeks-scheduler-overlay-tail.bin",
    )
    parser.add_argument(
        "--scheduler-payload", type=Path,
        default=ROOT / "build/boot/scheduler-overlay.prg",
    )
    parser.add_argument(
        "--scheduler-page", type=Path,
        default=ROOT / "build/8502/udeks-scheduler-overlay-page.bin",
    )
    parser.add_argument(
        "--task-switch-tail", type=Path,
        default=ROOT / "build/8502/task-switch-tail.bin",
    )
    parser.add_argument(
        "--task-context-vectors", type=Path,
        default=ROOT / "build/8502/task-context-vectors.bin",
    )
    parser.add_argument(
        "--boot-delivery", type=Path,
        default=ROOT / "build/boot/8502-boot-delivery.bin",
    )
    parser.add_argument(
        "--capability", type=Path,
        default=ROOT / "build/boot/8502-capability.bin",
    )
    parser.add_argument(
        "--capability-installer", type=Path,
        default=ROOT / "build/boot/capability-installer.bin",
    )
    parser.add_argument(
        "--boot-console", type=Path,
        default=ROOT / "build/boot/8502-boot-console.bin",
    )
    parser.add_argument(
        "--task-activation", type=Path,
        default=ROOT / "build/boot/task-switch-activation.bin",
    )
    parser.add_argument("--work", type=Path, default=ROOT / "build/vice")
    parser.add_argument("--task-loader", type=Path, default=ROOT/'build/boot/task-loader.bin')
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

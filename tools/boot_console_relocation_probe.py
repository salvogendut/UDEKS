#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the relocated boot-only console composer under VICE.

Both native disk formats must retain an exact copy of the linked composer at
$1600 after startup.  The D71 run then starts xwave in application slot 2 and
proves that the now-dead boot image can be overwritten safely.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shadow_boot_probe as sp
from capability_relocation_probe import inject_until_state
from vice_capture import choose_port


ROOT = Path(__file__).resolve().parents[1]
BOOT_CONSOLE_ADDRESS = 0x1600
XWAVE_STATUS_STATE_ADDRESS = 0xF265
XWAVE_STATUS_RUNNING = 3


def probe_disk(
    disk: Path,
    boot_console: bytes,
    map_path: Path,
    work: Path,
    exercise_reuse: bool,
    timeout: float,
    flatpak_id: str,
) -> bytes:
    symbols = sp.symbol_addresses(map_path)
    port = choose_port()
    process, master_fd = sp.launch_vice(disk.resolve(), port, flatpak_id)
    try:
        print(f"{disk.name}: booting", flush=True)
        time.sleep(6.0)
        deadline = time.monotonic() + timeout
        sp.wait_for_byte(
            port,
            sp.ROOT_TERMINAL_STATUS_READY_ADDRESS,
            sp.ROOT_TERMINAL_STATUS_READY,
            deadline,
        )
        before_path = work / f"{disk.suffix[1:]}-slot2-at-start.bin"
        before = sp.capture_blocks(
            port,
            [
                (
                    before_path,
                    BOOT_CONSOLE_ADDRESS,
                    BOOT_CONSOLE_ADDRESS + len(boot_console) - 1,
                    "kernel",
                )
            ],
        )[0]
        before_path.write_bytes(before)
        if before != boot_console:
            raise RuntimeError(
                f"{disk.name}: slot 2 is not the linked boot-console image"
            )
        print(f"{disk.name}: slot 2 image matches", flush=True)

        if exercise_reuse:
            inject_until_state(
                port,
                symbols,
                "xinit",
                sp.VIC_STATUS_STATE_ADDRESS,
                sp.VIC_STATUS_ACTIVE,
                time.monotonic() + timeout,
            )
            inject_until_state(
                port,
                symbols,
                "xwave &",
                XWAVE_STATUS_STATE_ADDRESS,
                XWAVE_STATUS_RUNNING,
                time.monotonic() + timeout,
            )
            after_path = work / "d71-slot2-after-xwave.bin"
            after = sp.capture_blocks(
                port,
                [
                    (
                        after_path,
                        BOOT_CONSOLE_ADDRESS,
                        BOOT_CONSOLE_ADDRESS + len(boot_console) - 1,
                        "kernel",
                    )
                ],
            )[0]
            after_path.write_bytes(after)
            if after == before:
                raise RuntimeError("xwave did not overwrite boot-console slot 2")
            print(f"{disk.name}: xwave safely reused slot 2", flush=True)
        return before
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
        "--boot-console",
        type=Path,
        default=ROOT / "build/boot/8502-boot-console.bin",
    )
    parser.add_argument("--map", type=Path, default=ROOT / "build/8502/udeks-8502.map")
    parser.add_argument("--work", type=Path, default=ROOT / "build/vice/boot-console")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    boot_console = args.boot_console.read_bytes()
    try:
        d71 = probe_disk(
            args.d71,
            boot_console,
            args.map,
            args.work,
            True,
            args.timeout,
            args.flatpak_id,
        )
        d64 = probe_disk(
            args.d64,
            boot_console,
            args.map,
            args.work,
            False,
            args.timeout,
            args.flatpak_id,
        )
        if d71 != d64:
            raise RuntimeError("D71 and D64 initial slot-2 images differ")
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"boot-console relocation probe failed: {error}") from error
    print("boot-console relocation probe OK: D71/D64 match; xwave reused slot 2")


if __name__ == "__main__":
    main()

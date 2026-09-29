#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Boot a UDEKS disk in VICE and verify the installed scheduler image.

The probe waits for the console-ready status byte, then captures
$1C00-$1FFF and requires it to equal the linked scheduler image padded with
zeros (the boot delivery zero-fills the rest of the reserved page).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shadow_boot_probe as sp
from vice_capture import choose_port

ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_ADDRESS = 0x1C00
SCHEDULER_PAGE_SIZE = 0x0400
CONSOLE_STATUS_READY_ADDRESS = 0xF075
CONSOLE_STATUS_READY = 2


def probe(args: argparse.Namespace) -> None:
    scheduler = args.scheduler.read_bytes()
    if not scheduler:
        raise SystemExit("scheduler image is empty")
    if len(scheduler) > SCHEDULER_PAGE_SIZE:
        raise SystemExit("scheduler exceeds its $1C00-$1FFF reservation")
    expected = scheduler.ljust(SCHEDULER_PAGE_SIZE, b"\x00")
    port = choose_port()
    process, master_fd = sp.launch_vice(
        args.disk.resolve(), port, args.flatpak_id
    )
    try:
        time.sleep(6.0)
        deadline = time.monotonic() + args.timeout
        sp.wait_for_byte(
            port, CONSOLE_STATUS_READY_ADDRESS, CONSOLE_STATUS_READY, deadline
        )
        image = sp.capture_blocks(
            port,
            [
                (
                    args.work / "installed-scheduler.bin",
                    SCHEDULER_ADDRESS,
                    SCHEDULER_ADDRESS + SCHEDULER_PAGE_SIZE - 1,
                    "kernel",
                )
            ],
        )[0]
        if image != expected:
            first = next(
                offset
                for offset, (actual, wanted) in enumerate(
                    zip(image, expected)
                )
                if actual != wanted
            )
            raise SystemExit(
                f"installed scheduler differs at "
                f"${SCHEDULER_ADDRESS + first:04X}: "
                f"${image[first]:02X} != ${expected[first]:02X}"
            )
        print(
            f"{args.disk.name}: scheduler image matches "
            f"({len(scheduler)} bytes, zero-filled to "
            f"{SCHEDULER_PAGE_SIZE})"
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(image)
    finally:
        sp.terminate(process, port)
        try:
            os.close(master_fd)
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disk", type=Path, required=True)
    parser.add_argument(
        "--scheduler", type=Path,
        default=ROOT / "build/8502/udeks-scheduler.bin",
    )
    parser.add_argument(
        "--work", type=Path, default=ROOT / "build/vice"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    try:
        probe(args)
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"scheduler delivery probe failed: {error}") from error
    print("scheduler delivery probe OK")


if __name__ == "__main__":
    main()

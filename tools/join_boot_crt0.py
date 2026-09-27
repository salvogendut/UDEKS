#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Join boot-only services, boot pages, scheduler, installer, and kernel.

The development PRG loads from $0200 and carries the post-stage-1 memory
image: the boot-only capability service in application slot 1, the probe page,
the gathered scheduler and boot-console composer in application slot 2, crt0,
the resident kernel, and the protected $F7D8 copier sliced from the
stage1-gateway image.
Enter the result at $1C00 with SYS 7168.
"""

from __future__ import annotations

import argparse
from pathlib import Path


CAPABILITY_ADDRESS = 0x0200
CAPABILITY_SIZE = 0x03C7
CAPABILITY_BSS_SIZE = 1
PROBE_ADDRESS = 0x0B00
PROBE_SIZE = 0x0100
SCHEDULER_ADDRESS = 0x1200
SCHEDULER_SIZE = 0x0400
BOOT_CONSOLE_ADDRESS = 0x1600
BOOT_CONSOLE_SIZE = 0x05AA
TASK_SWITCH_ACTIVATION_SIZE = 42
CRT0_ADDRESS = 0x1C00
CRT0_SIZE = 0x0100
KERNEL_ADDRESS = 0x2000
INSTALLER_ADDRESS = 0xF7D8
INSTALLER_BASE = 0xF700
INSTALLER_OFFSET = INSTALLER_ADDRESS - INSTALLER_BASE
INSTALLER_SIZE = 35


def join(
    capability: bytes,
    boot_console: bytes,
    probe: bytes,
    scheduler: bytes,
    crt0: bytes,
    kernel: bytes,
    gateway: bytes,
    destination: Path,
    task_activation: bytes = b"",
) -> None:
    if len(capability) != CAPABILITY_SIZE:
        raise ValueError(
            f"capability image is {len(capability)} bytes; expected "
            f"{CAPABILITY_SIZE}"
        )
    if len(probe) > PROBE_SIZE:
        raise ValueError(f"probe exceeds its {PROBE_SIZE}-byte page")
    if len(boot_console) != BOOT_CONSOLE_SIZE:
        raise ValueError(
            f"boot console image is {len(boot_console)} bytes; expected "
            f"{BOOT_CONSOLE_SIZE}"
        )
    if task_activation and len(task_activation) != TASK_SWITCH_ACTIVATION_SIZE:
        raise ValueError(
            f"task-switch activation is {len(task_activation)} bytes; expected "
            f"{TASK_SWITCH_ACTIVATION_SIZE}"
        )
    if not scheduler or len(scheduler) > SCHEDULER_SIZE:
        raise ValueError(f"scheduler exceeds its {SCHEDULER_SIZE}-byte slot")
    if len(crt0) > CRT0_SIZE:
        raise ValueError(f"crt0 exceeds its {CRT0_SIZE}-byte page")
    if not kernel:
        raise ValueError("resident kernel image is empty")
    installer = gateway[INSTALLER_OFFSET : INSTALLER_OFFSET + INSTALLER_SIZE]
    if len(installer) != INSTALLER_SIZE:
        raise ValueError("stage1 gateway is missing the $F7D8 copier")
    image = bytearray(capability)
    image.extend(bytes(CAPABILITY_BSS_SIZE))
    image.extend(bytes(PROBE_ADDRESS - (CAPABILITY_ADDRESS + len(image))))
    image.extend(probe.ljust(PROBE_SIZE, b"\x00"))
    image.extend(bytes(SCHEDULER_ADDRESS - (PROBE_ADDRESS + PROBE_SIZE)))
    image.extend(scheduler.ljust(SCHEDULER_SIZE, b"\x00"))
    if CAPABILITY_ADDRESS + len(image) != BOOT_CONSOLE_ADDRESS:
        raise ValueError("scheduler slot does not end at the boot console")
    image.extend(boot_console)
    image.extend(task_activation)
    image.extend(bytes(CRT0_ADDRESS - (CAPABILITY_ADDRESS + len(image))))
    image.extend(crt0.ljust(CRT0_SIZE, b"\x00"))
    image.extend(bytes(KERNEL_ADDRESS - (CRT0_ADDRESS + CRT0_SIZE)))
    image.extend(kernel)
    image.extend(bytes(INSTALLER_ADDRESS - (KERNEL_ADDRESS + len(kernel))))
    image.extend(installer)
    if CAPABILITY_ADDRESS + len(image) > 0x10000:
        raise ValueError("direct image extends beyond the 16-bit address space")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(image)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capability", type=Path)
    parser.add_argument("boot_console", type=Path)
    parser.add_argument("probe", type=Path)
    parser.add_argument("scheduler", type=Path)
    parser.add_argument("crt0", type=Path)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("gateway", type=Path)
    parser.add_argument("--task-switch-activation", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        join(
            args.capability.read_bytes(),
            args.boot_console.read_bytes(),
            args.probe.read_bytes(),
            args.scheduler.read_bytes(),
            args.crt0.read_bytes(),
            args.kernel.read_bytes(),
            args.gateway.read_bytes(),
            args.destination,
            b"" if args.task_switch_activation is None else args.task_switch_activation.read_bytes(),
        )
    except (OSError, ValueError) as error:
        raise SystemExit(f"cannot join direct boot image: {error}") from error


if __name__ == "__main__":
    main()

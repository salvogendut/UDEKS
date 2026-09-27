#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Join the capability service, boot pages, scheduler, installer, and kernel.

The development PRG loads from $0200 and carries the post-stage-1 memory
image: the boot-only capability service in application slot 1, the probe page,
the gathered scheduler in the temporary application slot, crt0, the resident
kernel, and the protected $F7D8 copier sliced from the stage1-gateway image.
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
CRT0_ADDRESS = 0x1C00
CRT0_SIZE = 0x0100
KERNEL_ADDRESS = 0x2000
INSTALLER_ADDRESS = 0xF7D8
INSTALLER_BASE = 0xF700
INSTALLER_OFFSET = INSTALLER_ADDRESS - INSTALLER_BASE
INSTALLER_SIZE = 35


def join(
    capability: bytes,
    probe: bytes,
    scheduler: bytes,
    crt0: bytes,
    kernel: bytes,
    gateway: bytes,
    destination: Path,
) -> None:
    if len(capability) != CAPABILITY_SIZE:
        raise ValueError(
            f"capability image is {len(capability)} bytes; expected "
            f"{CAPABILITY_SIZE}"
        )
    if len(probe) > PROBE_SIZE:
        raise ValueError(f"probe exceeds its {PROBE_SIZE}-byte page")
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
    image.extend(scheduler)
    image.extend(bytes(CRT0_ADDRESS - (SCHEDULER_ADDRESS + len(scheduler))))
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
    parser.add_argument("probe", type=Path)
    parser.add_argument("scheduler", type=Path)
    parser.add_argument("crt0", type=Path)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("gateway", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        join(
            args.capability.read_bytes(),
            args.probe.read_bytes(),
            args.scheduler.read_bytes(),
            args.crt0.read_bytes(),
            args.kernel.read_bytes(),
            args.gateway.read_bytes(),
            args.destination,
        )
    except (OSError, ValueError) as error:
        raise SystemExit(f"cannot join direct boot image: {error}") from error


if __name__ == "__main__":
    main()

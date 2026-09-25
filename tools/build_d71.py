#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the deterministic native-boot UDEKS D71 image."""

from __future__ import annotations

import argparse
from pathlib import Path


SECTOR_SIZE = 256
TRACK_COUNT = 70
STAGE1_ADDRESS = 0x1C00
KERNEL_ADDRESS = 0x2000
Z80_STAGING_ADDRESS = 0xD000
TASK_LOADER_STAGING_ADDRESS = 0xC800
TASK_LOADER_STAGING_SIZE = 0x05F0
TASK_REQUEST_STAGING_ADDRESS = 0xC300
TASK_REQUEST_STAGING_SIZE = 0x0109
BOOTFS_REQUEST_STAGING_ADDRESS = 0xC4EF
BOOTFS_REQUEST_STAGING_SIZE = 0x0311
TASK_BANK_GATE_STAGING_ADDRESS = 0xCE00
TASK_BANK_GATE_STAGING_SIZE = 0x00CB
Z80_SIZE = 0x2000
APP_IMAGE_SIZE = 0x0A00
APP1_STAGING_ADDRESS = 0xAF00
APP2_STAGING_ADDRESS = 0xB900
USH_ALLOCATION_SIZE = 0x0A00
BOOTFS_Z80_OFFSET = 0x0800
BOOTFS_SIZE = 0x1800
PAYLOAD_SIZE = 0xD400
PAYLOAD_BLOCKS = PAYLOAD_SIZE // SECTOR_SIZE


def sectors_per_track(track: int) -> int:
    if not 1 <= track <= TRACK_COUNT:
        raise ValueError(f"track {track} is outside a D71")
    side_track = track if track <= 35 else track - 35
    if side_track <= 17:
        return 21
    if side_track <= 24:
        return 19
    if side_track <= 30:
        return 18
    return 17


def sector_offset(track: int, sector: int) -> int:
    count = sectors_per_track(track)
    if not 0 <= sector < count:
        raise ValueError(f"sector {track}/{sector} is outside a D71")
    earlier = sum(sectors_per_track(number) for number in range(1, track))
    return (earlier + sector) * SECTOR_SIZE


def blank_d71(name: str = "UDEKS", disk_id: str = "01") -> bytearray:
    if not 1 <= len(name) <= 16 or len(disk_id) != 2:
        raise ValueError("disk name must be 1..16 characters and id exactly 2")
    image = bytearray(
        sum(sectors_per_track(track) for track in range(1, TRACK_COUNT + 1))
        * SECTOR_SIZE
    )
    bam = sector_offset(18, 0)
    image[bam : bam + 4] = bytes((18, 1, 0x41, 0x80))
    for track in range(1, 36):
        count = sectors_per_track(track)
        bits = (1 << count) - 1
        entry = bam + 4 + (track - 1) * 4
        image[entry] = count
        image[entry + 1 : entry + 4] = bits.to_bytes(3, "little")

    encoded_name = name.upper().encode("ascii")
    image[bam + 0x90 : bam + 0xA0] = encoded_name.ljust(16, b"\xa0")
    image[bam + 0xA2 : bam + 0xA4] = disk_id.encode("ascii")
    image[bam + 0xA4 : bam + 0xA8] = b"\xa02A\xa0"

    bam2 = sector_offset(53, 0)
    for track in range(36, 71):
        count = sectors_per_track(track)
        bits = (1 << count) - 1
        bitmap = bam2 + (track - 36) * 3
        image[bitmap : bitmap + 3] = bits.to_bytes(3, "little")
        image[bam + 0xDD + (track - 36)] = count

    # DOS reserves the primary BAM, first directory sector, and all of the
    # secondary-side BAM track exactly as a freshly formatted D71 does.
    mark_used(image, 18, 0)
    mark_used(image, 18, 1)
    directory = sector_offset(18, 1)
    image[directory : directory + 2] = b"\x00\xff"
    for sector in range(sectors_per_track(53)):
        mark_used(image, 53, sector)
    return image


def mark_used(image: bytearray, track: int, sector: int) -> None:
    bam = sector_offset(18, 0)
    if track <= 35:
        entry = bam + 4 + (track - 1) * 4
        count_offset = entry
        bitmap = entry + 1
    else:
        count_offset = bam + 0xDD + (track - 36)
        bitmap = sector_offset(53, 0) + (track - 36) * 3
    byte_offset = bitmap + sector // 8
    mask = 1 << (sector & 7)
    if image[byte_offset] & mask:
        image[byte_offset] &= ~mask
        image[count_offset] -= 1


def boot_locations(blocks: int):
    track = 1
    sector = 0
    for _ in range(blocks):
        yield track, sector
        sector += 1
        if sector == sectors_per_track(track):
            track += 1
            sector = 0


def install_app_image(
    kernel: bytearray, image: bytes, address: int, name: str
) -> None:
    if len(image) > APP_IMAGE_SIZE:
        raise ValueError(f"{name} image exceeds its 2560-byte reservation")
    offset = address - KERNEL_ADDRESS
    if any(kernel[offset : offset + APP_IMAGE_SIZE]):
        raise ValueError(f"{name} staging range overlaps resident kernel data")
    kernel[offset : offset + APP_IMAGE_SIZE] = image.ljust(
        APP_IMAGE_SIZE, b"\x00"
    )


def install_bootfs(z80: bytearray, bootfs: bytes) -> None:
    if len(bootfs) > BOOTFS_SIZE:
        raise ValueError(f"bootfs exceeds its {BOOTFS_SIZE}-byte reservation")
    region = z80[BOOTFS_Z80_OFFSET : BOOTFS_Z80_OFFSET + BOOTFS_SIZE]
    if any(region):
        raise ValueError("bootfs overlaps Z80 code or data")
    z80[BOOTFS_Z80_OFFSET : BOOTFS_Z80_OFFSET + BOOTFS_SIZE] = (
        bootfs.ljust(BOOTFS_SIZE, b"\x00")
    )


def validate_ush(bootfs: bytes, executable: bytes) -> None:
    if not executable:
        return
    if len(executable) < 16 or executable[:4] != b"UDEX":
        raise ValueError("ush is not a UDEX executable")
    major, minor, cpu, flags = executable[4:8]
    load_address = int.from_bytes(executable[8:10], "little")
    image_size = int.from_bytes(executable[10:12], "little")
    bss_size = int.from_bytes(executable[12:14], "little")
    entry_address = int.from_bytes(executable[14:16], "little")
    if major != 0 or minor > 1:
        raise ValueError("ush has an unsupported UDEX version")
    if cpu != 1:
        raise ValueError("ush is not an 8502 executable")
    if flags != 0x01:
        raise ValueError("ush is not a persistent-poll executable")
    if load_address != 0x9000 or entry_address != 0x9000:
        raise ValueError("ush must load and enter at $9000")
    if image_size == 0 or len(executable) != 16 + image_size:
        raise ValueError("ush UDEX image size is inconsistent")
    if image_size + bss_size > USH_ALLOCATION_SIZE:
        raise ValueError("ush exceeds its 2560-byte bank-1 allocation")
    if len(bootfs) < 40 or bootfs[:4] != b"UBFS" or bootfs[6] == 0:
        raise ValueError("bootfs cannot provide /bin/ush")
    entry = None
    for index in range(bootfs[6]):
        candidate = 16 + index * 24
        if candidate + 24 > len(bootfs):
            raise ValueError("bootfs directory is truncated")
        name_size = bootfs[candidate + 1]
        if name_size == 3 and bootfs[candidate + 8 : candidate + 11] == b"ush":
            entry = candidate
            break
    if entry is None:
        raise ValueError("bootfs does not contain /bin/ush")
    file_offset = int.from_bytes(bootfs[entry + 2 : entry + 4], "little")
    file_size = int.from_bytes(bootfs[entry + 4 : entry + 6], "little")
    if file_size != len(executable) or bootfs[
        file_offset : file_offset + file_size
    ] != executable:
        raise ValueError("bootfs ush entry does not match the staged executable")


def install_task_loader(kernel: bytearray, loader: bytes) -> None:
    if len(loader) > TASK_LOADER_STAGING_SIZE:
        raise ValueError(
            f"task loader exceeds its {TASK_LOADER_STAGING_SIZE}-byte staging area"
        )
    offset = TASK_LOADER_STAGING_ADDRESS - KERNEL_ADDRESS
    region = kernel[offset : offset + TASK_LOADER_STAGING_SIZE]
    if any(region):
        raise ValueError("task-loader staging overlaps resident kernel data")
    kernel[offset : offset + TASK_LOADER_STAGING_SIZE] = loader.ljust(
        TASK_LOADER_STAGING_SIZE, b"\x00"
    )


def install_task_request_gateway(kernel: bytearray, gateway: bytes) -> None:
    if len(gateway) > TASK_REQUEST_STAGING_SIZE:
        raise ValueError(
            f"task request gateway exceeds its {TASK_REQUEST_STAGING_SIZE}-byte staging area"
        )
    offset = TASK_REQUEST_STAGING_ADDRESS - KERNEL_ADDRESS
    region = kernel[offset : offset + TASK_REQUEST_STAGING_SIZE]
    if any(region):
        raise ValueError("task-request staging overlaps resident kernel data")
    kernel[offset : offset + TASK_REQUEST_STAGING_SIZE] = gateway.ljust(
        TASK_REQUEST_STAGING_SIZE, b"\x00"
    )


def install_bootfs_request_service(kernel: bytearray, service: bytes) -> None:
    if len(service) > BOOTFS_REQUEST_STAGING_SIZE:
        raise ValueError(
            f"bootfs request service exceeds its {BOOTFS_REQUEST_STAGING_SIZE}-byte staging area"
        )
    offset = BOOTFS_REQUEST_STAGING_ADDRESS - KERNEL_ADDRESS
    region = kernel[offset : offset + BOOTFS_REQUEST_STAGING_SIZE]
    if any(region):
        raise ValueError("bootfs-request staging overlaps resident kernel data")
    kernel[offset : offset + BOOTFS_REQUEST_STAGING_SIZE] = service.ljust(
        BOOTFS_REQUEST_STAGING_SIZE, b"\x00"
    )


def install_task_bank_gateway(kernel: bytearray, gateway: bytes) -> None:
    if len(gateway) > TASK_BANK_GATE_STAGING_SIZE:
        raise ValueError("task-bank gateway exceeds its 203-byte staging area")
    offset = TASK_BANK_GATE_STAGING_ADDRESS - KERNEL_ADDRESS
    region = kernel[offset : offset + TASK_BANK_GATE_STAGING_SIZE]
    if any(region):
        raise ValueError("task-bank gateway staging overlaps resident kernel data")
    kernel[offset : offset + TASK_BANK_GATE_STAGING_SIZE] = gateway.ljust(
        TASK_BANK_GATE_STAGING_SIZE, b"\x00"
    )


def build_image(
    stage0: bytes, stage1: bytes, kernel: bytes, z80: bytes,
    app1: bytes = b"", app2: bytes = b"", bootfs: bytes = b"",
    task_loader: bytes = b"", task_bank_gateway: bytes = b"",
    task_request_gateway: bytes = b"",
    bootfs_request_service: bytes = b"",
    ush: bytes = b"",
) -> bytes:
    if len(stage0) > SECTOR_SIZE:
        raise ValueError("stage 0 exceeds one sector")
    if stage0[:3] != b"CBM":
        raise ValueError("stage 0 is missing the CBM autoboot signature")
    if stage0[3:7] != b"\x00\x1c\x00\xd4":
        raise ValueError("stage-0 load address, bank, or block count is wrong")
    if len(stage1) > KERNEL_ADDRESS - STAGE1_ADDRESS:
        raise ValueError("stage 1 exceeds $1C00-$1FFF")
    if len(kernel) > Z80_STAGING_ADDRESS - KERNEL_ADDRESS:
        raise ValueError("kernel overlaps the bank-0 Z80 staging area")
    if len(z80) > Z80_SIZE:
        raise ValueError("Z80 image exceeds its 8 KiB reservation")

    staged_z80 = bytearray(z80.ljust(Z80_SIZE, b"\x00"))
    install_bootfs(staged_z80, bootfs)
    staged_kernel = bytearray(
        kernel.ljust(Z80_STAGING_ADDRESS - KERNEL_ADDRESS, b"\x00")
    )
    install_app_image(staged_kernel, app1, APP1_STAGING_ADDRESS, "application 1")
    install_app_image(staged_kernel, app2, APP2_STAGING_ADDRESS, "application 2")
    validate_ush(bootfs, ush)
    install_task_request_gateway(staged_kernel, task_request_gateway)
    install_bootfs_request_service(staged_kernel, bootfs_request_service)
    install_task_loader(staged_kernel, task_loader)
    install_task_bank_gateway(staged_kernel, task_bank_gateway)

    payload = (
        stage1.ljust(KERNEL_ADDRESS - STAGE1_ADDRESS, b"\x00")
        + staged_kernel
        + staged_z80
    )
    if len(payload) != PAYLOAD_SIZE:
        raise AssertionError("native boot payload layout drifted")

    image = blank_d71()
    sectors = [stage0.ljust(SECTOR_SIZE, b"\x00")]
    sectors.extend(
        payload[offset : offset + SECTOR_SIZE]
        for offset in range(0, len(payload), SECTOR_SIZE)
    )
    for (track, sector), data in zip(
        boot_locations(1 + PAYLOAD_BLOCKS), sectors, strict=True
    ):
        offset = sector_offset(track, sector)
        image[offset : offset + SECTOR_SIZE] = data
        mark_used(image, track, sector)
    return bytes(image)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage0", type=Path, required=True)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--z80", type=Path, required=True)
    parser.add_argument("--app1", type=Path)
    parser.add_argument("--app2", type=Path)
    parser.add_argument("--bootfs", type=Path)
    parser.add_argument("--task-loader", type=Path)
    parser.add_argument("--task-bank-gateway", type=Path)
    parser.add_argument("--task-request-gateway", type=Path)
    parser.add_argument("--bootfs-request-service", type=Path)
    parser.add_argument("--ush", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    try:
        image = build_image(
            args.stage0.read_bytes(),
            args.stage1.read_bytes(),
            args.kernel.read_bytes(),
            args.z80.read_bytes(),
            b"" if args.app1 is None else args.app1.read_bytes(),
            b"" if args.app2 is None else args.app2.read_bytes(),
            b"" if args.bootfs is None else args.bootfs.read_bytes(),
            b"" if args.task_loader is None else args.task_loader.read_bytes(),
            b"" if args.task_bank_gateway is None else args.task_bank_gateway.read_bytes(),
            b"" if args.task_request_gateway is None else args.task_request_gateway.read_bytes(),
            b"" if args.bootfs_request_service is None else args.bootfs_request_service.read_bytes(),
            b"" if args.ush is None else args.ush.read_bytes(),
        )
    except ValueError as error:
        raise SystemExit(f"cannot build D71: {error}") from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)


if __name__ == "__main__":
    main()

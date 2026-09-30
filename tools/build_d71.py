#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the deterministic native-boot UDEKS D71 image."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SECTOR_SIZE = 256
TRACK_COUNT = 70
D64_TRACK_COUNT = 35
D64_SIZE = sum(
    (21 if track <= 17 else 19 if track <= 24 else 18 if track <= 30 else 17)
    * SECTOR_SIZE
    for track in range(1, D64_TRACK_COUNT + 1)
)
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
TASK_BANK_GATE_STAGING_SIZE = 0x00C0
Z80_SIZE = 0x2000
CRT0_STAGING_ADDRESS = 0xAE00
CRT0_SIZE = 0x0100
PROBE_STAGING_ADDRESS = 0xAD00
PROBE_SIZE = 0x0100
BOOTFS_TAIL_STAGING_ADDRESS = 0xAF00
SCHEDULER_SIZE = 0x0400
BOOT_DELIVERY_SIZE = 0x010B
CAPABILITY_SIZE = 0x03C7
BOOT_CONSOLE_SIZE = 0x05AA
BOOT_CONSOLE_DESTINATION = 0x1600
TASK_SWITCH_ACTIVATION_SIZE = 42
BOOT_CONSOLE_INSTALLER_ADDRESS = 0x0B50
BUSY_SPRITE_ADDRESS = 0x0BC0
BUSY_SPRITE_SIZE = 63
SCHEDULER_TAIL_INSTALLER_STAGING_ADDRESS = 0xC409
SCHEDULER_TAIL_INSTALLER_SIZE = 0x00C0
SCATTER_MANIFEST_MAX = 7 + 4 * 8
SCATTER_MANIFEST_ADDRESS = PROBE_STAGING_ADDRESS - SCATTER_MANIFEST_MAX
SCATTER_TEMP_ADDRESS = 0x1200
BOOT_SECTOR_BASE = 0x0B00
BOOT_SECTOR_SIZE = 0x0100
SYSCALL_PAGE = 0xCF00
MODULE_STAGING_ADDRESS = 0xBFBB
MODULE_STAGING_SIZE = 0x0344
USH_ALLOCATION_SIZE = 0x1000
BOOTFS_Z80_OFFSET = 0x0300
BOOTFS_Z80_SIZE = 0x1D00
BOOTFS_TAIL_SIZE = 0x1400
BOOTFS_SIZE = BOOTFS_Z80_SIZE + BOOTFS_TAIL_SIZE
PAYLOAD_SIZE = 0xD400
PAYLOAD_BLOCKS = PAYLOAD_SIZE // SECTOR_SIZE
SCHEDULER_OVERLAY_NAME = "SCHEDOVR"


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


def d64_compatibility_image(image: bytes) -> bytes:
    """Return side one of a standard D71 as a Pi1541-compatible D64."""
    expected_size = sum(
        sectors_per_track(track) for track in range(1, TRACK_COUNT + 1)
    ) * SECTOR_SIZE
    if len(image) != expected_size:
        raise ValueError("D64 compatibility source is not a standard D71 image")
    result = bytearray(image[:D64_SIZE])
    # A single-sided derivative must not advertise a D71 second BAM.
    result[sector_offset(18, 0)+3] &= 0x7f
    return bytes(result)


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


def sector_is_free(image: bytes, track: int, sector: int) -> bool:
    if track > D64_TRACK_COUNT:
        return False
    bam = sector_offset(18, 0)
    entry = bam + 4 + (track - 1) * 4
    return bool(image[entry + 1 + sector // 8] & (1 << (sector & 7)))


def install_prg_file(image: bytearray, name: str, data: bytes, *, file_type: int = 0x82) -> None:
    """Install a closed PRG (or raw-byte SEQ) on side one, also visible in D64."""
    if file_type not in (0x81, 0x82):
        raise ValueError("disk file must be closed SEQ or PRG")
    if not data and file_type != 0x81:
        raise ValueError("disk PRG is empty")
    try:
        encoded = name.upper().encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("disk filename must be ASCII") from error
    if not 1 <= len(encoded) <= 16:
        raise ValueError("disk filename must be 1..16 characters")
    blocks = max(1, (len(data) + 253) // 254)
    available: list[tuple[int, int]] = []
    for track in range(1, D64_TRACK_COUNT + 1):
        if track == 18:
            continue
        for sector in range(sectors_per_track(track)):
            if sector_is_free(image, track, sector):
                available.append((track, sector))
                if len(available) == blocks:
                    break
        if len(available) == blocks:
            break
    if len(available) != blocks:
        raise ValueError("side one has no room for disk PRG")

    directory = sector_offset(18, 1)
    entry = None
    seen = set()
    while entry is None:
        if directory in seen:
            raise ValueError("cyclic disk directory")
        seen.add(directory)
        for slot in range(8):
            candidate = directory + 2 + slot * 32
            if image[candidate] == 0:
                entry = candidate
                break
        if entry is not None:
            break
        if image[directory]:
            if image[directory] != 18 or not image[directory+1]:
                raise ValueError("invalid disk directory link")
            directory = sector_offset(18, image[directory+1])
        else:
            free = next((s for s in range(2, sectors_per_track(18))
                         if sector_is_free(image, 18, s)), None)
            if free is None:
                raise ValueError("disk directory is full")
            image[directory:directory+2] = bytes((18, free))
            directory = sector_offset(18, free)
            image[directory:directory+256] = b'\0\xff' + bytes(254)
            mark_used(image, 18, free)

    for index, (track, sector) in enumerate(available):
        chunk = data[index * 254 : (index + 1) * 254]
        offset = sector_offset(track, sector)
        if index + 1 < len(available):
            image[offset] = available[index + 1][0]
            image[offset + 1] = available[index + 1][1]
        else:
            image[offset] = 0
            image[offset + 1] = len(chunk) + 1
        image[offset + 2 : offset + 2 + len(chunk)] = chunk
        mark_used(image, track, sector)

    image[entry] = file_type
    image[entry + 1] = available[0][0]
    image[entry + 2] = available[0][1]
    image[entry + 3 : entry + 19] = encoded.ljust(16, b"\xa0")
    # Directory entries begin at sector offset 2; the block count is at
    # sector-relative bytes 30-31, hence entry-relative bytes 28-29.
    image[entry + 28 : entry + 30] = blocks.to_bytes(2, "little")


def boot_locations(blocks: int):
    track = 1
    sector = 0
    for _ in range(blocks):
        yield track, sector
        sector += 1
        if sector == sectors_per_track(track):
            track += 1
            sector = 0


def install_bootfs(z80: bytearray, kernel: bytearray, bootfs: bytes) -> None:
    if len(bootfs) > BOOTFS_SIZE:
        raise ValueError(f"bootfs exceeds its {BOOTFS_SIZE}-byte reservation")
    padded = bootfs.ljust(BOOTFS_SIZE, b"\x00")
    z80_region = z80[
        BOOTFS_Z80_OFFSET : BOOTFS_Z80_OFFSET + BOOTFS_Z80_SIZE
    ]
    if any(z80_region):
        raise ValueError("bootfs overlaps Z80 code or data")
    tail_offset = BOOTFS_TAIL_STAGING_ADDRESS - KERNEL_ADDRESS
    kernel_region = kernel[tail_offset : tail_offset + BOOTFS_TAIL_SIZE]
    if any(kernel_region):
        raise ValueError("bootfs tail staging overlaps resident kernel data")
    z80[BOOTFS_Z80_OFFSET : BOOTFS_Z80_OFFSET + BOOTFS_Z80_SIZE] = (
        padded[:BOOTFS_Z80_SIZE]
    )
    kernel[tail_offset : tail_offset + BOOTFS_TAIL_SIZE] = (
        padded[BOOTFS_Z80_SIZE:]
    )


def install_crt0(kernel: bytearray, crt0: bytes) -> None:
    if len(crt0) > CRT0_SIZE:
        raise ValueError(
            f"crt0 exceeds its {CRT0_SIZE}-byte reservation"
        )
    if CRT0_STAGING_ADDRESS + CRT0_SIZE > BOOTFS_TAIL_STAGING_ADDRESS:
        raise ValueError("crt0 staging is not below bootfs staging")
    offset = CRT0_STAGING_ADDRESS - KERNEL_ADDRESS
    region = kernel[offset : offset + CRT0_SIZE]
    if any(region):
        raise ValueError("crt0 staging overlaps resident kernel data")
    kernel[offset : offset + CRT0_SIZE] = crt0.ljust(CRT0_SIZE, b"\x00")


def install_probe(kernel: bytearray, probe: bytes) -> None:
    if len(probe) > PROBE_SIZE:
        raise ValueError(
            f"probe exceeds its {PROBE_SIZE}-byte reservation"
        )
    if PROBE_STAGING_ADDRESS + PROBE_SIZE > CRT0_STAGING_ADDRESS:
        raise ValueError("probe staging is not below crt0 staging")
    offset = PROBE_STAGING_ADDRESS - KERNEL_ADDRESS
    region = kernel[offset : offset + PROBE_SIZE]
    if any(region):
        raise ValueError("probe staging overlaps resident kernel data")
    kernel[offset : offset + PROBE_SIZE] = probe.ljust(PROBE_SIZE, b"\x00")


BOOTFS_REQUEST_COPIED_SIZE = 0x029B


def shadow_start_from_map(map_text: str) -> int:
    match = re.search(
        r"^VICSHADOW\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)",
        map_text,
        re.MULTILINE,
    )
    if match is None:
        raise ValueError("VICSHADOW segment is missing from the linker map")
    return int(match.group(1), 16)


def scheduler_holes(
    shadow_start: int, stage0_end: int, capability_size: int = 0
) -> list[list[int]]:
    regions = [
        (PROBE_STAGING_ADDRESS, PROBE_SIZE),
        (CRT0_STAGING_ADDRESS, CRT0_SIZE),
        (BOOTFS_TAIL_STAGING_ADDRESS, BOOTFS_TAIL_SIZE),
        (MODULE_STAGING_ADDRESS, MODULE_STAGING_SIZE),
        (TASK_REQUEST_STAGING_ADDRESS, TASK_REQUEST_STAGING_SIZE),
        (BOOTFS_REQUEST_STAGING_ADDRESS, BOOTFS_REQUEST_COPIED_SIZE),
        (TASK_LOADER_STAGING_ADDRESS, TASK_LOADER_STAGING_SIZE),
        (TASK_BANK_GATE_STAGING_ADDRESS, TASK_BANK_GATE_STAGING_SIZE),
    ]
    if capability_size:
        regions.append((shadow_start, capability_size))
    regions.sort()
    holes: list[list[int]] = []
    cursor = shadow_start
    for start, size in regions:
        if start > cursor:
            holes.append([cursor, start - 1])
        cursor = max(cursor, start + size)
    if cursor <= SYSCALL_PAGE - 1:
        holes.append([cursor, SYSCALL_PAGE - 1])
    holes.append([stage0_end + 1, BOOT_SECTOR_BASE + BOOT_SECTOR_SIZE - 1])
    return sorted(holes)


def scheduler_layout(
    shadow_start: int, stage0_end: int, scheduler_size: int,
    capability_size: int = 0,
) -> tuple[tuple[int, int], list[tuple[int, int]], int]:
    """Manifest, chunk regions, and delivery ceiling for the given size."""
    holes = scheduler_holes(shadow_start, stage0_end, capability_size)
    manifest_start = SCATTER_MANIFEST_ADDRESS
    manifest_end = manifest_start + SCATTER_MANIFEST_MAX - 1
    manifest_hole = None
    for index, (start, end) in enumerate(holes):
        if start <= manifest_start and manifest_end <= end:
            manifest_hole = index
            break
    if manifest_hole is None:
        raise ValueError("scatter manifest is outside the free payload holes")
    hole_start, hole_end = holes[manifest_hole]
    replacement: list[list[int]] = []
    if hole_start <= manifest_start - 1:
        replacement.append([hole_start, manifest_start - 1])
    if manifest_end + 1 <= hole_end:
        replacement.append([manifest_end + 1, hole_end])
    holes[manifest_hole : manifest_hole + 1] = replacement
    ceiling = sum(end - start + 1 for start, end in holes)
    chunks: list[tuple[int, int]] = []
    offset = 0
    for start, end in holes:
        if offset >= scheduler_size:
            break
        take = min(end - start + 1, scheduler_size - offset)
        if take <= 0:
            continue
        chunks.append((start, take))
        offset += take
    if offset < scheduler_size:
        raise ValueError(
            f"scheduler needs {scheduler_size} bytes; the scatter holes "
            f"deliver at most {ceiling}"
        )
    if len(chunks) > 8:
        raise ValueError("scatter manifest entry limit exceeded")
    return (manifest_start, manifest_end), chunks, ceiling


def install_scheduler(
    kernel: bytearray,
    boot_sector: bytearray,
    scheduler: bytes,
    shadow_start: int,
    capability_size: int = 0,
    boot_sector_reserved_end: int | None = None,
) -> None:
    if len(scheduler) > SCHEDULER_SIZE:
        raise ValueError(
            f"scheduler exceeds its {SCHEDULER_SIZE}-byte reservation"
        )
    if not scheduler:
        raise ValueError("scheduler image is empty")
    stage0_end = (
        max(
            (offset for offset, byte in enumerate(boot_sector) if byte),
            default=0,
        )
        + BOOT_SECTOR_BASE
    )
    if boot_sector_reserved_end is not None:
        stage0_end = max(stage0_end, boot_sector_reserved_end)
    (manifest_start, manifest_end), chunk_regions, _ = scheduler_layout(
        shadow_start, stage0_end, len(scheduler), capability_size
    )
    chunks: list[tuple[int, int, int]] = []
    offset = 0
    for start, take in chunk_regions:
        chunks.append((start, take, offset))
        offset += take
    checksum = sum(scheduler) & 0xFFFF
    manifest = bytearray(b"USCT")
    manifest.append(len(chunks))
    manifest += checksum.to_bytes(2, "little")
    for start, take, _ in chunks:
        manifest += start.to_bytes(2, "little")
        manifest += take.to_bytes(2, "little")
    kernel_offset = manifest_start - KERNEL_ADDRESS
    if any(kernel[kernel_offset : kernel_offset + len(manifest)]):
        raise ValueError("scatter manifest overlaps resident kernel data")
    kernel[kernel_offset : kernel_offset + len(manifest)] = manifest
    for start, take, chunk_offset in chunks:
        data = scheduler[chunk_offset : chunk_offset + take]
        if start < BOOT_SECTOR_BASE + BOOT_SECTOR_SIZE:
            sector_start = start - BOOT_SECTOR_BASE
            if any(boot_sector[sector_start : sector_start + take]):
                raise ValueError("scheduler chunk overlaps boot-sector data")
            boot_sector[sector_start : sector_start + take] = data
        else:
            offset = start - KERNEL_ADDRESS
            if any(kernel[offset : offset + take]):
                raise ValueError("scheduler chunk overlaps resident kernel data")
            kernel[offset : offset + take] = data


def install_capability(
    kernel: bytearray, capability: bytes, shadow_start: int
) -> None:
    if len(capability) != CAPABILITY_SIZE:
        raise ValueError(
            f"capability image is {len(capability)} bytes; expected "
            f"{CAPABILITY_SIZE}"
        )
    end = shadow_start + len(capability)
    if end > SCATTER_MANIFEST_ADDRESS:
        raise ValueError("capability staging reaches the scheduler manifest")
    offset = shadow_start - KERNEL_ADDRESS
    region = kernel[offset : offset + len(capability)]
    if len(region) != len(capability) or any(region):
        raise ValueError("capability staging overlaps resident kernel data")
    kernel[offset : offset + len(capability)] = capability


def install_boot_delivery(
    kernel: bytearray, boot_delivery: bytes, shadow_start: int
) -> None:
    if len(boot_delivery) != BOOT_DELIVERY_SIZE:
        raise ValueError(
            f"boot delivery image is {len(boot_delivery)} bytes; expected "
            f"{BOOT_DELIVERY_SIZE}"
        )
    offset = shadow_start - KERNEL_ADDRESS
    region = kernel[offset : offset + len(boot_delivery)]
    if len(region) != len(boot_delivery) or any(region):
        raise ValueError("boot delivery staging overlaps resident kernel data")
    kernel[offset : offset + len(boot_delivery)] = boot_delivery


def install_capability_installer(
    kernel: bytearray, installer: bytes, shadow_start: int
) -> None:
    if not installer:
        raise ValueError("capability installer is empty")
    start = shadow_start + CAPABILITY_SIZE
    end = start + len(installer)
    if end > SCATTER_MANIFEST_ADDRESS:
        raise ValueError("capability installer reaches the scheduler manifest")
    offset = start - KERNEL_ADDRESS
    region = kernel[offset : offset + len(installer)]
    if len(region) != len(installer) or any(region):
        raise ValueError("capability installer overlaps staged data")
    kernel[offset : offset + len(installer)] = installer


def install_boot_console(
    kernel: bytearray,
    boot_console: bytes,
    task_activation: bytes,
    shadow_start: int,
    capability_size: int,
    capability_installer_size: int,
) -> None:
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
    installed_image = boot_console + task_activation
    start = shadow_start + capability_size + capability_installer_size
    end = start + len(installed_image)
    if end > PROBE_STAGING_ADDRESS:
        raise ValueError("boot console staging reaches the probe staging page")
    offset = start - KERNEL_ADDRESS
    region = kernel[offset : offset + len(installed_image)]
    if len(region) != len(installed_image) or any(region):
        raise ValueError("boot console staging overlaps resident kernel data")
    kernel[offset : offset + len(installed_image)] = installed_image


def install_boot_console_installer(
    boot_sector: bytearray, installer: bytes
) -> None:
    if not installer:
        raise ValueError("boot console installer is empty")
    offset = BOOT_CONSOLE_INSTALLER_ADDRESS - BOOT_SECTOR_BASE
    end = offset + len(installer)
    if end > BOOT_SECTOR_SIZE:
        raise ValueError("boot console installer exceeds the boot-sector page")
    region = boot_sector[offset:end]
    if len(region) != len(installer) or any(region):
        raise ValueError("boot console installer overlaps stage 0")
    boot_sector[offset:end] = installer


def install_busy_sprite(boot_sector: bytearray, sprite: bytes) -> None:
    if len(sprite) != BUSY_SPRITE_SIZE:
        raise ValueError(
            f"busy sprite is {len(sprite)} bytes; expected {BUSY_SPRITE_SIZE}"
        )
    offset = BUSY_SPRITE_ADDRESS - BOOT_SECTOR_BASE
    end = offset + len(sprite)
    region = boot_sector[offset:end]
    if len(region) != len(sprite) or any(region):
        raise ValueError("busy sprite overlaps boot-sector data")
    boot_sector[offset:end] = sprite


def install_scheduler_tail_installer(
    kernel: bytearray, installer: bytes
) -> None:
    if len(installer) != SCHEDULER_TAIL_INSTALLER_SIZE:
        raise ValueError(
            f"scheduler tail installer is {len(installer)} bytes; expected "
            f"{SCHEDULER_TAIL_INSTALLER_SIZE}"
        )
    offset = SCHEDULER_TAIL_INSTALLER_STAGING_ADDRESS - KERNEL_ADDRESS
    region = kernel[offset : offset + len(installer)]
    if len(region) != len(installer) or any(region):
        raise ValueError("scheduler tail installer overlaps staged data")
    kernel[offset : offset + len(installer)] = installer


def install_module(kernel: bytearray, module: bytes) -> None:
    if len(module) > MODULE_STAGING_SIZE:
        raise ValueError(
            f"high-memory module exceeds its {MODULE_STAGING_SIZE}-byte reservation"
        )
    offset = MODULE_STAGING_ADDRESS - KERNEL_ADDRESS
    region = kernel[offset : offset + MODULE_STAGING_SIZE]
    if any(region):
        raise ValueError("high-memory module overlaps bootfs or kernel staging")
    kernel[offset : offset + MODULE_STAGING_SIZE] = module.ljust(
        MODULE_STAGING_SIZE, b"\x00"
    )


def validate_persistent_shell(executable: bytes) -> None:
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
        raise ValueError("ush exceeds its 4096-byte bank-1 allocation")
    if len(executable) > 0x1000:
        raise ValueError("ush file exceeds bootstrap staging before $1200")


def validate_ush(bootfs: bytes, executable: bytes) -> None:
    if not executable:
        return
    validate_persistent_shell(executable)
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
    if file_offset + file_size > len(bootfs):
        raise ValueError("bootfs ush is truncated")
    # Recovery may omit startup support; validate it independently rather
    # than forcing the disk shell and its recovery image to be identical.
    validate_persistent_shell(bootfs[file_offset:file_offset+file_size])


def validate_command(executable: bytes) -> None:
    """Ordinary APP1 executable, independent of a particular utility name."""
    if (len(executable) < 17 or executable[:4] != b'UDEX' or
            executable[4] != 0 or executable[5] > 1 or executable[6:8] != b'\x01\0'):
        raise ValueError('invalid ordinary command header')
    load, size, bss, entry = (int.from_bytes(executable[n:n+2], 'little') for n in (8, 10, 12, 14))
    if load != 0x0200 or not size or len(executable) != 16+size or size+bss > 0x0a00:
        raise ValueError('command exceeds APP1 or file bounds')
    if not load <= entry < load+size:
        raise ValueError('command entry outside image')


def validate_managed_app(executable: bytes, base: int) -> None:
    """Fixed-slot managed UDEX and all six entry veneers, before packaging."""
    if (len(executable) < 34 or executable[:4] != b'UDEX' or
            executable[4] != 0 or executable[5] > 1 or executable[6:8] != b'\x01\x02'):
        raise ValueError('invalid managed UDEX header or callback table')
    load, size, bss, entry = (int.from_bytes(executable[n:n+2], 'little')
                              for n in (8, 10, 12, 14))
    if base not in (0x0200, 0x1200) or load != base or entry != base:
        raise ValueError('managed application targets the wrong slot or entry')
    if len(executable) != 16+size or size < 18 or size+bss > 0x0A00:
        raise ValueError('managed application size exceeds its slot or file')
    for n in range(16, 34, 3):
        target = int.from_bytes(executable[n+1:n+3], 'little')
        if executable[n] != 0x4c or not base+18 <= target < base+size:
            raise ValueError('managed callback must JMP inside its own image')


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
        raise ValueError("task-bank gateway exceeds its 192-byte staging area")
    offset = TASK_BANK_GATE_STAGING_ADDRESS - KERNEL_ADDRESS
    region = kernel[offset : offset + TASK_BANK_GATE_STAGING_SIZE]
    if any(region):
        raise ValueError("task-bank gateway staging overlaps resident kernel data")
    kernel[offset : offset + TASK_BANK_GATE_STAGING_SIZE] = gateway.ljust(
        TASK_BANK_GATE_STAGING_SIZE, b"\x00"
    )


def build_image(
    stage0: bytes, stage1: bytes, kernel: bytes, z80: bytes,
    bootfs: bytes = b"", module: bytes = b"",
    task_loader: bytes = b"", task_bank_gateway: bytes = b"",
    task_request_gateway: bytes = b"",
    bootfs_request_service: bytes = b"",
    ush: bytes = b"", crt0: bytes = b"", probe: bytes = b"",
    scheduler: bytes = b"", shadow_start: int | None = None,
    capability: bytes = b"",
    capability_installer: bytes = b"",
    boot_console: bytes = b"",
    task_activation: bytes = b"",
    boot_console_installer: bytes = b"",
    boot_delivery: bytes = b"",
    scheduler_overlay: bytes = b"",
    scheduler_tail_installer: bytes = b"",
    busy_sprite: bytes = b"",
    secondary_bootfs: bool = False,
    hello: bytes | None = None,
    rc: bytes | None = None,
    sysinfo: bytes = b"",
    xclock: bytes = b"",
    xwave: bytes = b"",
    commands: tuple[tuple[str, bytes], ...] = (),
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

    staged_kernel = bytearray(
        kernel.ljust(Z80_STAGING_ADDRESS - KERNEL_ADDRESS, b"\x00")
    )
    staged_z80 = bytearray(z80.ljust(Z80_SIZE, b"\x00"))
    install_probe(staged_kernel, probe)
    install_crt0(staged_kernel, crt0)
    if secondary_bootfs:
        from build_storage import install_bootfs as install_secondary_bootfs
        scheduler_overlay = install_secondary_bootfs(scheduler_overlay, bootfs)
    else:
        install_bootfs(staged_z80, staged_kernel, bootfs)
    install_module(staged_kernel, module)
    validate_ush(bootfs, ush)
    install_task_request_gateway(staged_kernel, task_request_gateway)
    if scheduler_tail_installer:
        install_scheduler_tail_installer(staged_kernel, scheduler_tail_installer)
    install_bootfs_request_service(staged_kernel, bootfs_request_service)
    install_task_loader(staged_kernel, task_loader)
    install_task_bank_gateway(staged_kernel, task_bank_gateway)
    stage0_sector = bytearray(stage0.ljust(SECTOR_SIZE, b"\x00"))
    if busy_sprite:
        install_busy_sprite(stage0_sector, busy_sprite)
    delivery_size = len(boot_delivery)
    delivery_end = None if shadow_start is None else shadow_start + delivery_size
    if boot_delivery:
        if shadow_start is None:
            raise ValueError("boot delivery staging requires the shadow start")
        install_boot_delivery(staged_kernel, boot_delivery, shadow_start)
    if capability:
        if shadow_start is None:
            raise ValueError("capability staging requires the shadow start")
        install_capability(staged_kernel, capability, delivery_end)
        install_capability_installer(
            staged_kernel, capability_installer, delivery_end
        )
    if boot_console:
        if shadow_start is None:
            raise ValueError("boot console staging requires the shadow start")
        install_boot_console(
            staged_kernel,
            boot_console,
            task_activation,
            delivery_end,
            len(capability),
            len(capability_installer),
        )
        install_boot_console_installer(
            stage0_sector, boot_console_installer
        )
    if scheduler:
        if shadow_start is None:
            raise ValueError("scheduler staging requires the shadow start")
        install_scheduler(
            staged_kernel, stage0_sector, scheduler, shadow_start,
            delivery_size + len(capability) + len(capability_installer)
            + len(boot_console) + len(task_activation),
            (
                BOOT_CONSOLE_INSTALLER_ADDRESS
                + len(boot_console_installer) - 1
                if boot_console_installer else None
            ),
        )

    payload = (
        stage1.ljust(KERNEL_ADDRESS - STAGE1_ADDRESS, b"\x00")
        + staged_kernel
        + staged_z80
    )
    if len(payload) != PAYLOAD_SIZE:
        raise AssertionError("native boot payload layout drifted")

    image = blank_d71()
    sectors = [bytes(stage0_sector)]
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
    if scheduler_overlay:
        install_prg_file(
            image, SCHEDULER_OVERLAY_NAME, scheduler_overlay
        )
    if hello is not None:
        install_prg_file(image, "HELLO", hello, file_type=0x81)
    if ush:
        # Raw UDEX, not a KERNAL PRG: the persistent loader validates the
        # header before copying it into bank 1. Bootfs keeps a recovery copy.
        install_prg_file(image, "USH", ush, file_type=0x81)
    if rc is not None:
        install_prg_file(image, "RC", rc, file_type=0x81)
    if sysinfo:
        install_prg_file(image, "FREE", sysinfo, file_type=0x81)
        install_prg_file(image, "DF", sysinfo, file_type=0x81)
    for name, executable, base in (("XCLOCK", xclock, 0x0200), ("XWAVE", xwave, 0x1200)):
        if executable:
            validate_managed_app(executable, base)
            install_prg_file(image, name, executable, file_type=0x81)
    names = {'SCHEDOVR', 'USH', 'RC', 'HELLO', 'FREE', 'DF', 'XCLOCK', 'XWAVE'}
    for name, executable in commands:
        if name in names or not name or len(name) > 16 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in name):
            raise ValueError('invalid or duplicate disk command name')
        names.add(name)
        validate_command(executable)
        install_prg_file(image, name, executable, file_type=0x81)
    return bytes(image)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage0", type=Path, required=True)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--boot-delivery", type=Path, required=True)
    parser.add_argument("--crt0", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--scheduler", type=Path)
    parser.add_argument("--scheduler-overlay", type=Path, required=True)
    parser.add_argument("--scheduler-tail-installer", type=Path, required=True)
    parser.add_argument("--busy-sprite", type=Path, required=True)
    parser.add_argument("--capability", type=Path, required=True)
    parser.add_argument("--capability-installer", type=Path, required=True)
    parser.add_argument("--boot-console", type=Path, required=True)
    parser.add_argument("--task-switch-activation", type=Path, required=True)
    parser.add_argument(
        "--boot-console-installer", type=Path, required=True
    )
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--z80", type=Path, required=True)
    parser.add_argument("--bootfs", type=Path)
    parser.add_argument("--secondary-bootfs", action="store_true",
                        help="deliver bootfs directly in bank 1 via SCHEDOVR")
    parser.add_argument("--module", type=Path)
    parser.add_argument("--task-loader", type=Path)
    parser.add_argument("--task-bank-gateway", type=Path)
    parser.add_argument("--task-request-gateway", type=Path)
    parser.add_argument("--bootfs-request-service", type=Path)
    parser.add_argument("--ush", type=Path)
    parser.add_argument("--hello", type=Path, help="include a raw SEQ HELLO file for cat")
    parser.add_argument("--rc", type=Path, help="optional ASCII shell startup file")
    parser.add_argument("--sysinfo", type=Path, help="standalone FREE/DF multicall UDEX")
    parser.add_argument("--xclock", type=Path, help="disk-only managed XCLOCK UDEX")
    parser.add_argument("--xwave", type=Path, help="disk-only managed XWAVE UDEX")
    from build_bootfs import parse_entry
    parser.add_argument("--command", action="append", type=parse_entry, default=[], metavar="NAME=UDEX")
    parser.add_argument(
        "--d64-output",
        type=Path,
        help="also write a side-one D64 for drives that do not support D71",
    )
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    try:
        image = build_image(
            args.stage0.read_bytes(),
            args.stage1.read_bytes(),
            args.kernel.read_bytes(),
            args.z80.read_bytes(),
            b"" if args.bootfs is None else args.bootfs.read_bytes(),
            b"" if args.module is None else args.module.read_bytes(),
            b"" if args.task_loader is None else args.task_loader.read_bytes(),
            b"" if args.task_bank_gateway is None else args.task_bank_gateway.read_bytes(),
            b"" if args.task_request_gateway is None else args.task_request_gateway.read_bytes(),
            b"" if args.bootfs_request_service is None else args.bootfs_request_service.read_bytes(),
            b"" if args.ush is None else args.ush.read_bytes(),
            args.crt0.read_bytes(),
            args.probe.read_bytes(),
            b"" if args.scheduler is None else args.scheduler.read_bytes(),
            shadow_start_from_map(args.map.read_text(encoding="utf-8")),
            args.capability.read_bytes(),
            args.capability_installer.read_bytes(),
            args.boot_console.read_bytes(),
            args.task_switch_activation.read_bytes(),
            args.boot_console_installer.read_bytes(),
            args.boot_delivery.read_bytes(),
            args.scheduler_overlay.read_bytes(),
            args.scheduler_tail_installer.read_bytes(),
            args.busy_sprite.read_bytes(),
            args.secondary_bootfs,
            None if args.hello is None else args.hello.read_bytes(),
            None if args.rc is None else args.rc.read_bytes(),
            b"" if args.sysinfo is None else args.sysinfo.read_bytes(),
            b"" if args.xclock is None else args.xclock.read_bytes(),
            b"" if args.xwave is None else args.xwave.read_bytes(),
            tuple((name, path.read_bytes()) for name, path in args.command),
        )
    except ValueError as error:
        raise SystemExit(f"cannot build D71: {error}") from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    if args.d64_output is not None:
        args.d64_output.parent.mkdir(parents=True, exist_ok=True)
        args.d64_output.write_bytes(d64_compatibility_image(image))


if __name__ == "__main__":
    main()

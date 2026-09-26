# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_d71 import (
    BOOTFS_SIZE,
    BOOTFS_TAIL_STAGING_ADDRESS,
    BOOTFS_Z80_OFFSET,
    CRT0_SIZE,
    CRT0_STAGING_ADDRESS,
    D64_SIZE,
    BOOTFS_REQUEST_STAGING_ADDRESS,
    BOOTFS_REQUEST_STAGING_SIZE,
    MODULE_STAGING_ADDRESS,
    MODULE_STAGING_SIZE,
    PAYLOAD_BLOCKS,
    PAYLOAD_SIZE,
    SECTOR_SIZE,
    TASK_LOADER_STAGING_ADDRESS,
    TASK_LOADER_STAGING_SIZE,
    TASK_BANK_GATE_STAGING_ADDRESS,
    TASK_BANK_GATE_STAGING_SIZE,
    TASK_REQUEST_STAGING_ADDRESS,
    TASK_REQUEST_STAGING_SIZE,
    USH_ALLOCATION_SIZE,
    blank_d71,
    boot_locations,
    build_image,
    d64_compatibility_image,
    sector_offset,
)
from build_bootfs import build_bootfs


def stage0() -> bytes:
    return b"CBM\x00\x1c\x00\xd4" + bytes(25)


def ush_executable(
    payload: bytes = b"shell-code", *, bss_size: int = 3, flags: int = 1
) -> bytes:
    return (
        b"UDEX" + bytes((0, 1, 1, flags)) + b"\x00\x90"
        + len(payload).to_bytes(2, "little")
        + bss_size.to_bytes(2, "little") + b"\x00\x90" + payload
    )


def bootfs_with_ush(executable: bytes) -> bytes:
    return build_bootfs([("cowsay", b"x"), ("ush", executable)])


class BuildD71Tests(unittest.TestCase):
    def test_blank_image_has_standard_size_and_directory(self):
        image = blank_d71()
        self.assertEqual(len(image), 349696)
        self.assertEqual(image[sector_offset(18, 1) : sector_offset(18, 1) + 2], b"\x00\xff")

    def test_d64_compatibility_image_is_standard_first_side(self):
        image = build_image(stage0(), b"", b"", b"")
        d64 = d64_compatibility_image(image)
        self.assertEqual(len(d64), D64_SIZE)
        self.assertEqual(d64[:4], b"CBM\x00")
        self.assertEqual(d64, image[:D64_SIZE])

    def test_d64_compatibility_image_rejects_nonstandard_source(self):
        with self.assertRaisesRegex(ValueError, "standard D71"):
            d64_compatibility_image(bytes(D64_SIZE))

    def test_native_payload_round_trips_from_sequential_sectors(self):
        first = b"stage-one"
        kernel = b"kernel"
        z80 = b"z80"
        image = build_image(stage0(), first, kernel, z80)
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        self.assertEqual(len(payload), PAYLOAD_SIZE)
        self.assertEqual(payload[: len(first)], first)
        self.assertEqual(payload[0x400 : 0x400 + len(kernel)], kernel)
        self.assertEqual(payload[0xB400 : 0xB400 + len(z80)], z80)

    def test_boot_blocks_are_reserved_in_bam(self):
        image = build_image(stage0(), b"", b"", b"")
        bam = sector_offset(18, 0)
        self.assertEqual(image[bam + 4], 0)
        self.assertEqual(image[bam + 8], 0)
        self.assertEqual(image[bam + 44], 18)

    def test_high_memory_module_is_packed_after_bootfs_data(self):
        module = b"module"
        image = build_image(stage0(), b"", b"", b"", module=module)
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = MODULE_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(module)], module)

    def test_bootfs_is_packed_into_unused_z80_staging(self):
        bootfs = b"UBFS" + bytes(20)
        image = build_image(stage0(), b"", b"", b"", bootfs=bootfs)
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        z80 = payload[0xB400 : 0xB400 + 0x2000]
        self.assertEqual(
            z80[BOOTFS_Z80_OFFSET : BOOTFS_Z80_OFFSET + len(bootfs)],
            bootfs,
        )

    def test_persistent_ush_is_resolved_from_bootfs(self):
        executable = ush_executable()
        bootfs = bootfs_with_ush(executable)
        image = build_image(stage0(), b"", b"", b"", bootfs=bootfs,
                            ush=executable)
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        z80 = payload[0xB400 : 0xB400 + 0x2000]
        self.assertEqual(
            z80[BOOTFS_Z80_OFFSET : BOOTFS_Z80_OFFSET + len(bootfs)], bootfs
        )

    def test_ush_bootfs_validation_is_independent_of_directory_position(self):
        executable = ush_executable()
        bootfs = build_bootfs([
            ("aardvark", b"first"), ("cowsay", b"x"), ("ush", executable),
        ])
        build_image(stage0(), b"", b"", b"", bootfs=bootfs, ush=executable)

    def test_rejects_nonpersistent_ush(self):
        executable = ush_executable(b"x", bss_size=0, flags=0)
        with self.assertRaisesRegex(ValueError, "persistent-poll"):
            build_image(stage0(), b"", b"", b"",
                        bootfs=bootfs_with_ush(executable), ush=executable)

    def test_rejects_oversize_ush_allocation(self):
        executable = ush_executable(bytes(USH_ALLOCATION_SIZE), bss_size=1)
        with self.assertRaisesRegex(ValueError, "2560-byte"):
            build_image(stage0(), b"", b"", b"",
                        bootfs=bootfs_with_ush(executable), ush=executable)

    def test_task_request_gateway_is_staged_in_vic_shadow(self):
        gateway = b"request-gateway"
        image = build_image(
            stage0(), b"", b"", b"", task_request_gateway=gateway
        )
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = TASK_REQUEST_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(gateway)], gateway)

    def test_rejects_oversize_task_request_gateway(self):
        with self.assertRaisesRegex(ValueError, "265-byte"):
            build_image(
                stage0(), b"", b"", b"",
                task_request_gateway=bytes(TASK_REQUEST_STAGING_SIZE + 1),
            )

    def test_crt0_is_staged_below_bootfs_staging(self):
        crt0 = b"crt0-image"
        image = build_image(stage0(), b"", b"", b"", crt0=crt0)
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = CRT0_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(crt0)], crt0)
        self.assertLessEqual(
            CRT0_STAGING_ADDRESS + CRT0_SIZE, BOOTFS_TAIL_STAGING_ADDRESS
        )

    def test_rejects_oversize_crt0(self):
        with self.assertRaisesRegex(ValueError, "256-byte"):
            build_image(
                stage0(), b"", b"", b"", crt0=bytes(CRT0_SIZE + 1)
            )

    def test_rejects_crt0_staging_collision(self):
        kernel = bytes(CRT0_STAGING_ADDRESS - 0x2000) + b"x"
        with self.assertRaisesRegex(ValueError, "crt0 staging overlaps"):
            build_image(stage0(), b"", kernel, b"", crt0=b"c")

    def test_task_loader_is_staged_in_reclaimable_vic_shadow(self):
        loader = b"task-loader"
        image = build_image(
            stage0(), b"", b"", b"", task_loader=loader
        )
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = TASK_LOADER_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(loader)], loader)

    def test_rejects_module_staging_collision(self):
        bootfs = bytes(BOOTFS_SIZE - MODULE_STAGING_SIZE) + b"x"
        with self.assertRaisesRegex(ValueError, "overlaps bootfs"):
            build_image(stage0(), b"", b"", b"", bootfs=bootfs, module=b"m")

    def test_rejects_oversize_module(self):
        with self.assertRaisesRegex(ValueError, "837-byte"):
            build_image(
                stage0(), b"", b"", b"",
                module=bytes(MODULE_STAGING_SIZE + 1),
            )

    def test_rejects_oversize_bootfs(self):
        with self.assertRaisesRegex(ValueError, "12544-byte"):
            build_image(
                stage0(), b"", b"", b"", bootfs=bytes(BOOTFS_SIZE + 1)
            )

    def test_rejects_oversize_task_loader(self):
        with self.assertRaisesRegex(ValueError, "1520-byte"):
            build_image(
                stage0(), b"", b"", b"",
                task_loader=bytes(TASK_LOADER_STAGING_SIZE + 1),
            )

    def test_bootfs_request_service_is_staged_in_vic_shadow(self):
        service = b"bootfs-request-service"
        image = build_image(
            stage0(), b"", b"", b"", bootfs_request_service=service
        )
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = BOOTFS_REQUEST_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(service)], service)

    def test_rejects_oversize_bootfs_request_service(self):
        with self.assertRaisesRegex(ValueError, "785-byte"):
            build_image(
                stage0(), b"", b"", b"",
                bootfs_request_service=bytes(BOOTFS_REQUEST_STAGING_SIZE + 1),
            )

    def test_task_bank_gateway_is_staged_below_syscall_page(self):
        gateway = b"UTG1" + bytes(12)
        image = build_image(
            stage0(), b"", b"", b"", task_bank_gateway=gateway
        )
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = TASK_BANK_GATE_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(gateway)], gateway)

    def test_rejects_oversize_task_bank_gateway(self):
        with self.assertRaisesRegex(ValueError, "203-byte"):
            build_image(
                stage0(), b"", b"", b"",
                task_bank_gateway=bytes(TASK_BANK_GATE_STAGING_SIZE + 1),
            )

    def test_rejects_header_layout_drift(self):
        bad = bytearray(stage0())
        bad[6] = 211
        with self.assertRaisesRegex(ValueError, "block count"):
            build_image(bytes(bad), b"", b"", b"")


if __name__ == "__main__":
    unittest.main()

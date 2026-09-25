# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_d71 import (
    APP1_STAGING_ADDRESS,
    APP2_STAGING_ADDRESS,
    APP_IMAGE_SIZE,
    BOOTFS_SIZE,
    BOOTFS_Z80_OFFSET,
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

    def test_application_slots_are_packed_into_vic_shadow_staging(self):
        app1 = b"clock"
        app2 = b"wave"
        image = build_image(stage0(), b"", b"", b"", app1, app2)
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        app1_offset = APP1_STAGING_ADDRESS - 0x1C00
        app2_offset = APP2_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[app1_offset : app1_offset + len(app1)], app1)
        self.assertEqual(payload[app2_offset : app2_offset + len(app2)], app2)

    def test_bootfs_is_packed_into_unused_z80_staging(self):
        bootfs = b"UBFS" + bytes(20)
        image = build_image(
            stage0(), b"", b"", b"", b"clock", b"wave", bootfs
        )
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

    def test_persistent_ush_is_loaded_directly_from_bootfs(self):
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

    def test_rejects_nonpersistent_ush(self):
        executable = ush_executable(b"x", bss_size=0, flags=0)
        with self.assertRaisesRegex(ValueError, "persistent-poll"):
            build_image(stage0(), b"", b"", b"",
                        bootfs=bootfs_with_ush(executable), ush=executable)

    def test_rejects_oversize_ush_allocation(self):
        executable = ush_executable(bytes(USH_ALLOCATION_SIZE), bss_size=1)
        with self.assertRaisesRegex(ValueError, "2048-byte"):
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
        with self.assertRaisesRegex(ValueError, "512-byte"):
            build_image(
                stage0(), b"", b"", b"",
                task_request_gateway=bytes(TASK_REQUEST_STAGING_SIZE + 1),
            )

    def test_task_loader_is_staged_in_reclaimable_vic_shadow(self):
        loader = b"task-loader"
        image = build_image(
            stage0(), b"", b"", b"", b"", b"", b"", loader
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

    def test_rejects_application_staging_collision(self):
        kernel = bytearray(APP1_STAGING_ADDRESS - 0x2000 + 1)
        kernel[-1] = 1
        with self.assertRaisesRegex(ValueError, "overlaps resident kernel"):
            build_image(stage0(), b"", bytes(kernel), b"", b"app")

    def test_rejects_oversize_application(self):
        with self.assertRaisesRegex(ValueError, "2560-byte"):
            build_image(stage0(), b"", b"", b"", bytes(APP_IMAGE_SIZE + 1))

    def test_rejects_oversize_bootfs(self):
        with self.assertRaisesRegex(ValueError, "4096-byte"):
            build_image(
                stage0(), b"", b"", b"", b"", b"", bytes(BOOTFS_SIZE + 1)
            )

    def test_rejects_oversize_task_loader(self):
        with self.assertRaisesRegex(ValueError, "1280-byte"):
            build_image(
                stage0(), b"", b"", b"", b"", b"", b"",
                bytes(TASK_LOADER_STAGING_SIZE + 1),
            )

    def test_task_bank_gateway_is_staged_below_syscall_page(self):
        gateway = b"UTG1" + bytes(12)
        image = build_image(
            stage0(), b"", b"", b"", b"", b"", b"", b"", gateway
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
                stage0(), b"", b"", b"", b"", b"", b"", b"",
                bytes(TASK_BANK_GATE_STAGING_SIZE + 1),
            )

    def test_rejects_header_layout_drift(self):
        bad = bytearray(stage0())
        bad[6] = 211
        with self.assertRaisesRegex(ValueError, "block count"):
            build_image(bytes(bad), b"", b"", b"")


if __name__ == "__main__":
    unittest.main()

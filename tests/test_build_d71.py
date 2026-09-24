# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_d71 import (
    APP1_Z80_OFFSET,
    APP2_Z80_OFFSET,
    APP_IMAGE_SIZE,
    PAYLOAD_BLOCKS,
    PAYLOAD_SIZE,
    SECTOR_SIZE,
    blank_d71,
    boot_locations,
    build_image,
    sector_offset,
)


def stage0() -> bytes:
    return b"CBM\x00\x1c\x00\xd4" + bytes(25)


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

    def test_application_slots_are_packed_into_unused_z80_staging(self):
        app1 = b"clock"
        app2 = b"wave"
        image = build_image(stage0(), b"", b"", b"", app1, app2)
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        z80 = payload[0xB400 : 0xB400 + 0x2000]
        self.assertEqual(z80[APP1_Z80_OFFSET : APP1_Z80_OFFSET + len(app1)], app1)
        self.assertEqual(z80[APP2_Z80_OFFSET : APP2_Z80_OFFSET + len(app2)], app2)

    def test_rejects_application_staging_collision(self):
        z80 = bytearray(0x2000)
        z80[APP1_Z80_OFFSET] = 1
        with self.assertRaisesRegex(ValueError, "overlaps Z80"):
            build_image(stage0(), b"", b"", bytes(z80), b"app")

    def test_rejects_oversize_application(self):
        with self.assertRaisesRegex(ValueError, "2560-byte"):
            build_image(stage0(), b"", b"", b"", bytes(APP_IMAGE_SIZE + 1))

    def test_rejects_header_layout_drift(self):
        bad = bytearray(stage0())
        bad[6] = 211
        with self.assertRaisesRegex(ValueError, "block count"):
            build_image(bytes(bad), b"", b"", b"")


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_scheduler_overlay import (
    ABI_MAJOR,
    ABI_MINOR,
    HEADER_SIZE,
    LOAD_ADDRESS,
    MAGIC,
    build_overlay,
)


def overlay_map(image_size: int = 5, bss_size: int = 3) -> str:
    image_end = 0xC120 + image_size - 1
    bss_start = image_end + 1
    bss_end = bss_start + bss_size - 1
    return (
        "Segment list:\n-------------\n"
        "Name Start End Size Align\n"
        f"CODE 00C120 {image_end:06X} {image_size:06X} 00001\n"
        f"BSS {bss_start:06X} {bss_end:06X} {bss_size:06X} 00001\n"
    )


class SchedulerOverlayPayloadTests(unittest.TestCase):
    def test_envelope_records_load_placement_bss_and_checksum(self):
        image = b"abcde"
        payload = build_overlay(image, overlay_map())
        self.assertEqual(payload[:2], LOAD_ADDRESS.to_bytes(2, "little"))
        header = payload[2 : 2 + HEADER_SIZE]
        self.assertEqual(header[:4], MAGIC)
        self.assertEqual(header[4:6], bytes((ABI_MAJOR, ABI_MINOR)))
        self.assertEqual(int.from_bytes(header[6:8], "little"), 0xC120)
        self.assertEqual(int.from_bytes(header[8:10], "little"), len(image))
        self.assertEqual(int.from_bytes(header[10:12], "little"), 0xC125)
        self.assertEqual(int.from_bytes(header[12:14], "little"), 3)
        self.assertEqual(int.from_bytes(header[14:16], "little"), sum(image))
        self.assertEqual(payload[2 + HEADER_SIZE :], image)

    def test_map_and_image_drift_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "expected \\$C120"):
            build_overlay(b"abcde", overlay_map().replace("00C120", "00C121"))
        with self.assertRaisesRegex(ValueError, "map requires"):
            build_overlay(b"short", overlay_map(image_size=6))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            build_overlay(b"a", overlay_map(image_size=1, bss_size=0xDE0))


if __name__ == "__main__":
    unittest.main()

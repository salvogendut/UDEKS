# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vic_graphics_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(24)
    block[:4] = b"VICG"
    block[4] = 1
    block[5] = 3
    block[7:10] = b"\x01\x07\x00"
    block[10:17] = b"\xac\x00\x8c\x01\x60\x5c\xff"
    block[17:19] = (1).to_bytes(2, "little")
    return block


class VicGraphicsDecodeTests(unittest.TestCase):
    def test_accepts_active_black_on_yellow_surface(self):
        result = parse_result(valid_record())
        self.assertEqual(result["state"], 3)
        self.assertEqual(result["pointer_x"], 172)
        self.assertEqual(result["ram_bank"], 1)

    def test_accepts_stopped_surface(self):
        block = valid_record()
        block[5] = 2
        block[19:21] = (1).to_bytes(2, "little")
        result = parse_result(block)
        self.assertEqual(result["starts"], result["stops"])

    def test_rejects_wrong_memory_layout(self):
        block = valid_record()
        block[14] = 0x40
        with self.assertRaisesRegex(ValueError, "memory layout"):
            parse_result(block)

    def test_accepts_moved_pointer(self):
        block = valid_record()
        block[10:12] = (300).to_bytes(2, "little")
        block[12] = 200
        result = parse_result(block)
        self.assertEqual(result["pointer_x"], 300)
        self.assertEqual(result["pointer_y"], 200)

    def test_rejects_pointer_outside_visible_bounds(self):
        block = valid_record()
        block[10:12] = (400).to_bytes(2, "little")
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            parse_result(block)

    def test_rejects_active_surface_without_start(self):
        block = valid_record()
        block[17:19] = b"\x00\x00"
        with self.assertRaisesRegex(ValueError, "no initialization"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

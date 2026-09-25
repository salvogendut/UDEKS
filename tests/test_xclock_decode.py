# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from xclock_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(32)
    block[:4] = b"XCLK"
    block[4:8] = bytes((2, 3, 0, 7))
    block[8:12] = bytes((124, 61, 72, 77))
    block[12:15] = bytes((13, 45, 27))
    block[16:18] = (1).to_bytes(2, "little")
    block[18:20] = (4).to_bytes(2, "little")
    block[25] = 21
    return block


class XclockDecodeTests(unittest.TestCase):
    def test_accepts_running_clock(self):
        result = parse_result(valid_record())
        self.assertEqual(result["state"], 3)
        self.assertEqual(result["width"], 72)
        self.assertEqual(result["ticks"], 4)
        self.assertEqual(result["face_radius"], 21)

    def test_accepts_resized_clock(self):
        block = valid_record()
        block[8:12] = bytes((80, 40, 120, 100))
        result = parse_result(block)
        self.assertEqual(result["width"], 120)
        self.assertEqual(result["height"], 100)

    def test_accepts_legacy_fixed_geometry_record(self):
        block = valid_record()
        block[4] = 1
        block[25] = 0
        self.assertEqual(parse_result(block)["face_radius"], 21)

    def test_rejects_unrendered_running_clock(self):
        block = valid_record()
        block[16:18] = b"\x00\x00"
        with self.assertRaisesRegex(ValueError, "not rendered"):
            parse_result(block)

    def test_accepts_stopped_clock(self):
        block = valid_record()
        block[5] = 2
        block[22:24] = (1).to_bytes(2, "little")
        self.assertEqual(parse_result(block)["closes"], 1)


if __name__ == "__main__":
    unittest.main()

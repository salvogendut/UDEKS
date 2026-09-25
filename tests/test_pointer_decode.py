# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from pointer_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(32)
    block[:4] = b"PTRI"
    block[4] = 1
    block[5] = 2
    block[7] = 0x0F
    block[8:10] = (172).to_bytes(2, "little")
    block[10] = 140
    block[18:20] = (9).to_bytes(2, "little")
    return block


class PointerDecodeTests(unittest.TestCase):
    def test_accepts_dual_source_pointer_record(self):
        result = parse_result(valid_record())
        self.assertEqual(result["x"], 172)
        self.assertEqual(result["y"], 140)
        self.assertEqual(result["samples"], 9)

    def test_decodes_signed_motion(self):
        block = valid_record()
        block[16] = 0xFD
        block[17] = 3
        result = parse_result(block)
        self.assertEqual(result["dx"], -3)
        self.assertEqual(result["dy"], 3)

    def test_rejects_wrong_port_policy(self):
        block = valid_record()
        block[7] = 0x0E
        with self.assertRaisesRegex(ValueError, "capability flags"):
            parse_result(block)

    def test_rejects_out_of_bounds_position(self):
        block = valid_record()
        block[8:10] = (400).to_bytes(2, "little")
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

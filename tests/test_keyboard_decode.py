# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from keyboard_decode import parse_result


def valid_record():
    block = bytearray(48)
    block[:4] = b"KEYB"
    block[4] = 1
    block[5] = 2
    block[7] = 11
    block[8] = 16
    block[16] = 1
    block[17] = 0x0F
    block[18:20] = (123).to_bytes(2, "little")
    return block


def debounced_record():
    block = valid_record()
    block[4] = 2
    block[17] = 0x1F
    return block


class KeyboardDecodeTests(unittest.TestCase):
    def test_accepts_idle_full_matrix_driver(self):
        result = parse_result(valid_record())
        self.assertEqual(result["matrix_lines"], 11)
        self.assertEqual(result["polls"], 123)
        self.assertEqual(result["matrix"], [0] * 11)

    def test_accepts_normalized_key_event(self):
        block = valid_record()
        block[9] = 2
        block[11:15] = bytes((2, 10, ord("a"), 0))
        block[20] = 1
        block[22] = 1
        block[35:38] = bytes((10, ord("a"), 0))
        result = parse_result(block)
        self.assertEqual(result["last_scan_code"], 10)
        self.assertEqual(result["last_character"], ord("a"))
        self.assertEqual(result["last_press_character"], ord("a"))

    def test_accepts_debounced_driver_record(self):
        result = parse_result(debounced_record())
        self.assertEqual(result["format"], 2)
        self.assertEqual(result["flags"], 0x1F)

    def test_rejects_queue_overflow(self):
        block = valid_record()
        block[9] = 17
        with self.assertRaisesRegex(ValueError, "depth"):
            parse_result(block)

    def test_rejects_missing_extended_matrix(self):
        block = valid_record()
        block[7] = 8
        with self.assertRaisesRegex(ValueError, "geometry"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

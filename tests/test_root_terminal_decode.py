# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from root_terminal_decode import parse_result


def valid_record():
    block = bytearray(32)
    block[:4] = b"RCLI"
    block[4] = 1
    block[5] = 2
    block[7] = 54
    block[12:14] = (100).to_bytes(2, "little")
    block[27] = 0xFF
    return block


class RootTerminalDecodeTests(unittest.TestCase):
    def test_accepts_idle_editor(self):
        result = parse_result(valid_record())
        self.assertEqual(result["capacity"], 54)
        self.assertEqual(result["polls"], 100)

    def test_accepts_submission_diagnostics(self):
        block = valid_record()
        block[14:16] = (4).to_bytes(2, "little")
        block[16:18] = (3).to_bytes(2, "little")
        block[18:20] = (1).to_bytes(2, "little")
        block[20] = 3
        block[21:23] = (0x126).to_bytes(2, "little")
        block[24:26] = (4).to_bytes(2, "little")
        result = parse_result(block)
        self.assertEqual(result["submissions"], 1)
        self.assertEqual(result["last_length"], 3)
        self.assertEqual(result["last_checksum"], 0x126)

    def test_rejects_cursor_beyond_line(self):
        block = valid_record()
        block[8] = 2
        block[9] = 3
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            parse_result(block)

    def test_accepts_bounded_history_diagnostics(self):
        block = valid_record()
        block[26] = 3
        block[27] = 1
        block[28:30] = (5).to_bytes(2, "little")
        result = parse_result(block)
        self.assertEqual(result["history_count"], 3)
        self.assertEqual(result["history_position"], 1)
        self.assertEqual(result["history_recalls"], 5)

    def test_rejects_history_position_beyond_entries(self):
        block = valid_record()
        block[26] = 2
        block[27] = 2
        with self.assertRaisesRegex(ValueError, "history position"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

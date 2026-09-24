# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from time_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(24)
    block[:4] = b"TIME"
    block[4:8] = bytes((1, 2, 0, 1))
    block[8:12] = bytes((13, 45, 27, 4))
    block[16:18] = (100).to_bytes(2, "little")
    block[18:20] = (3).to_bytes(2, "little")
    block[20] = 1
    return block


class TimeDecodeTests(unittest.TestCase):
    def test_accepts_ready_cia_time(self):
        result = parse_result(valid_record())
        self.assertEqual((result["hour"], result["minute"]), (13, 45))
        self.assertEqual(result["polls"], 100)

    def test_rejects_invalid_clock_fields(self):
        block = valid_record()
        block[10] = 60
        with self.assertRaisesRegex(ValueError, "out of range"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

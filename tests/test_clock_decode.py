# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from clock_decode import parse_result


def valid_record() -> bytearray:
    return bytearray(b"CLK2\x01\x02\x00\x00\x01\x1b\x0b\x02\x07\x00\x00\x00")


class ClockDecodeTests(unittest.TestCase):
    def test_accepts_verified_2mhz_transition(self):
        result = parse_result(valid_record())
        self.assertEqual(result["requested_mhz"], 2)
        self.assertEqual(result["d030_after"] & 3, 1)
        self.assertEqual(result["d011_after"] & 0x10, 0)

    def test_rejects_service_failure(self):
        block = valid_record()
        block[5] = 0x83
        block[6] = 3
        with self.assertRaisesRegex(ValueError, "code 0x03"):
            parse_result(block)

    def test_rejects_test_mode(self):
        block = valid_record()
        block[8] = 3
        with self.assertRaisesRegex(ValueError, r"invalid \$D030"):
            parse_result(block)

    def test_rejects_visible_vic(self):
        block = valid_record()
        block[10] |= 0x10
        with self.assertRaisesRegex(ValueError, "VIC display remains enabled"):
            parse_result(block)

    def test_preserved_emulator_records_pass(self):
        result_root = ROOT / "bench/results/2026-09-24-clock-2mhz/raw"
        names = (
            "clock-vice-64.bin",
            "clock-vice-16.bin",
            "clock-1986-64.bin",
            "clock-1986-16.bin",
        )
        for name in names:
            with self.subTest(result=name):
                result = parse_result((result_root / name).read_bytes())
                self.assertEqual(result["requested_mhz"], 2)
                self.assertEqual(result["flags"], 0x07)


if __name__ == "__main__":
    unittest.main()

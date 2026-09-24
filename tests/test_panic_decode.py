# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from panic_decode import parse_result


def valid_record() -> bytearray:
    return bytearray(b"PANI\x01\x02\x22\x00\x35\x3e\x37\x03\x00\x00\x00\x00")


class PanicDecodeTests(unittest.TestCase):
    def test_accepts_service_descriptor_panic(self):
        result = parse_result(valid_record())
        self.assertEqual(result["code"], 0x22)
        self.assertEqual(result["vdc_flags"], 3)

    def test_rejects_unpublished_record(self):
        block = valid_record()
        block[5] = 1
        with self.assertRaisesRegex(ValueError, "not published"):
            parse_result(block)

    def test_rejects_incomplete_vdc_message(self):
        block = valid_record()
        block[11] = 1
        with self.assertRaisesRegex(ValueError, "VDC flags"):
            parse_result(block)

    def test_accepts_emulator_specific_mode_high_bit(self):
        block = valid_record()
        block[10] = 0xB7
        self.assertEqual(parse_result(block)["mode"], 0xB7)

    def test_preserved_emulator_records_pass(self):
        result_root = ROOT / "bench/results/2026-09-24-panic/raw"
        for name in ("vice-3.10.bin", "1986-7556c23.bin"):
            with self.subTest(result=name):
                result = parse_result((result_root / name).read_bytes())
                self.assertEqual(result["code"], 0x22)


if __name__ == "__main__":
    unittest.main()

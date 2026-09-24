# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vdc_console_decode import parse_result


def valid_record() -> bytearray:
    return bytearray(
        b"VCON\x01\x02\x00\x50\x19\x0f\x00\x08\x15\x0f\x00\x47"
        b"\xf0\x00\x00\x00\x00\x00\x00\x00"
    )


class VdcConsoleDecodeTests(unittest.TestCase):
    def test_accepts_verified_console(self):
        result = parse_result(valid_record())
        self.assertEqual(result["width"], 80)
        self.assertEqual(result["screen_readback"], 0x15)

    def test_reports_service_failure(self):
        block = valid_record()
        block[5] = 0x88
        block[6] = 8
        with self.assertRaisesRegex(ValueError, "code 0x08"):
            parse_result(block)

    def test_rejects_screen_readback_failure(self):
        block = valid_record()
        block[12] = 0x20
        with self.assertRaisesRegex(ValueError, "field 12"):
            parse_result(block)

    def test_rejects_disabled_attributes(self):
        block = valid_record()
        block[15] = 0x07
        with self.assertRaisesRegex(ValueError, "not enabled"):
            parse_result(block)

    def test_preserved_emulator_records_pass(self):
        result_root = ROOT / "bench/results/2026-09-24-vdc-console/raw"
        for name in ("vice-3.10.bin", "1986-7556c23.bin"):
            with self.subTest(result=name):
                result = parse_result((result_root / name).read_bytes())
                self.assertEqual(result["state"], 2)


if __name__ == "__main__":
    unittest.main()

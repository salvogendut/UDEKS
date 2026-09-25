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


def themed_record() -> bytearray:
    block = valid_record()
    block[4] = 2
    block[9] = 0
    block[13] = 0
    block[16] = 0x0D
    return block


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

    def test_accepts_black_on_yellow_theme(self):
        result = parse_result(themed_record())
        self.assertEqual(result["format"], 2)
        self.assertEqual(result["attribute"], 0)
        self.assertEqual(result["color"], 0x0D)

    def test_decodes_running_app_panel_state(self):
        block = themed_record()
        block[19] = 0x05
        block[20:22] = (3).to_bytes(2, "little")
        result = parse_result(block)
        self.assertEqual(result["app_mask"], 0x05)
        self.assertEqual(result["app_panel_updates"], 3)

    def test_rejects_unknown_running_app_bit(self):
        block = themed_record()
        block[19] = 0x80
        with self.assertRaisesRegex(ValueError, "unknown bits"):
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

# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from framebuffer_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(32)
    block[:4] = b"VFBR"
    block[4:24] = bytes(
        (
            1, 2, 0, 80, 200, 1, 16, 0x47, 0x87, 0, 0,
            20, 160, 30, 20, 0x5E, 0x06, 0x2E, 0x28, 0x1F,
        )
    )
    block[24] = 0x0D
    return block


class FramebufferDecodeTests(unittest.TestCase):
    def test_accepts_verified_splash(self):
        result = parse_result(valid_record())
        self.assertEqual(result["splash_address"], 0x065E)
        self.assertEqual(result["splash_checksum"], 0x282E)

    def test_accepts_64k_vdc(self):
        block = valid_record()
        block[10] = 64
        self.assertEqual(parse_result(block)["vdc_ram_kib"], 64)

    def test_reports_service_failure(self):
        block = valid_record()
        block[5] = 0x85
        block[6] = 5
        with self.assertRaisesRegex(ValueError, "code 0x05"):
            parse_result(block)

    def test_rejects_mode_inconsistency(self):
        block = valid_record()
        block[12] = 0x80
        with self.assertRaisesRegex(ValueError, "bitmap mode"):
            parse_result(block)

    def test_rejects_incomplete_upload(self):
        block = valid_record()
        block[23] = 0x17
        with self.assertRaisesRegex(ValueError, "field 23"):
            parse_result(block)

    def test_rejects_wrong_palette(self):
        block = valid_record()
        block[24] = 0x0F
        with self.assertRaisesRegex(ValueError, "field 24"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

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


def font_record() -> bytearray:
    block = valid_record()
    block[4] = 2
    block[23] = 0x7F
    block[25] = 5
    block[26] = 7
    block[27] = 9
    block[28] = 0x34
    block[29] = 0x12
    block[30] = 0x1F
    return block


def pipe_logo_record() -> bytearray:
    block = font_record()
    block[4] = 3
    block[15:23] = bytes((8, 64, 70, 12, 0x06, 0x04, 0x73, 0x58))
    return block


def left_pipe_logo_record() -> bytearray:
    block = pipe_logo_record()
    block[4] = 4
    block[17:21] = bytes((2, 12, 0xC2, 0x03))
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

    def test_accepts_verified_software_font_panel(self):
        result = parse_result(font_record())
        self.assertEqual(result["format"], 2)
        self.assertEqual(result["font_width"], 5)
        self.assertEqual(result["font_checksum"], 0x1234)

    def test_accepts_compact_pipe_logo_at_top_right(self):
        result = parse_result(pipe_logo_record())
        self.assertEqual(result["format"], 3)
        self.assertEqual(result["splash_address"], 0x0406)
        self.assertEqual(result["splash_checksum"], 0x5873)

    def test_accepts_compact_pipe_logo_at_top_left(self):
        result = parse_result(left_pipe_logo_record())
        self.assertEqual(result["format"], 4)
        self.assertEqual(result["splash_address"], 0x03C2)
        self.assertEqual(result["splash_checksum"], 0x5873)

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

    def test_preserved_font_records_pass(self):
        result_root = ROOT / "bench/results/2026-09-24-vdc-font/raw"
        names = ("vice-64.bin", "vice-16.bin", "1986-64.bin", "1986-16.bin")
        for name in names:
            with self.subTest(result=name):
                result = parse_result((result_root / name).read_bytes())
                self.assertEqual(result["format"], 2)
                self.assertEqual(result["flags"], 0x7F)

    def test_preserved_pipe_logo_records_pass(self):
        result_root = ROOT / "bench/results/2026-09-24-vdc-pipe-logo/raw"
        names = ("vice-64.bin", "vice-16.bin", "1986-64.bin", "1986-16.bin")
        for name in names:
            with self.subTest(result=name):
                result = parse_result((result_root / name).read_bytes())
                self.assertEqual(result["format"], 3)
                self.assertEqual(result["splash_address"], 0x0406)
                self.assertEqual(result["splash_checksum"], 0x5873)


if __name__ == "__main__":
    unittest.main()

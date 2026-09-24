# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from boot_status_decode import parse_result


def valid_block() -> bytearray:
    block = bytearray(16)
    block[:13] = b"UMMU\x01\x02\x3e\x09\x00\xf0\x01\xf0\xb1"
    return block


class BootStatusDecodeTests(unittest.TestCase):
    def test_accepts_expected_native_map(self):
        result = parse_result(valid_block())
        self.assertEqual(result["configuration"], 0x3E)
        self.assertEqual(result["page0_bank"], 0)
        self.assertEqual(result["page1_page"], 1)

    def test_rejects_wrong_configuration(self):
        block = valid_block()
        block[6] = 0x7E
        with self.assertRaisesRegex(ValueError, "MMU configuration"):
            parse_result(block)

    def test_rejects_bottom_common(self):
        block = valid_block()
        block[7] = 0x0D
        with self.assertRaisesRegex(ValueError, "RAM configuration"):
            parse_result(block)

    def test_rejects_z80_or_c64_mode(self):
        block = valid_block()
        block[12] = 0xB0
        with self.assertRaisesRegex(ValueError, "8502 C128 mode"):
            parse_result(block)

    def test_preserved_emulator_records_pass(self):
        result_root = ROOT / "bench/results/2026-09-24-memory-map-smoke/raw"
        for name in ("vice-3.10.bin", "1986-7556c23.bin"):
            with self.subTest(result=name):
                result = parse_result((result_root / name).read_bytes())
                self.assertEqual(result["configuration"], 0x3E)


if __name__ == "__main__":
    unittest.main()

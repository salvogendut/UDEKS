# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from xpm_to_vdc_text import build_package


class XpmToVdcTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = build_package(
            ROOT / "assets" / "udekspipe-64.xpm",
            ROOT / "assets" / "udekusu-64.xpm",
        )

    def test_package_preserves_lower_stock_character_set(self):
        self.assertEqual(self.package[:5], b"VTG1\x01")
        self.assertLessEqual(self.package[5], 128)
        self.assertEqual(self.package[6:10], bytes((8, 8, 8, 3)))

    def test_package_deduplicates_logo_tiles(self):
        glyph_count = self.package[5]
        self.assertEqual(glyph_count, 63)
        self.assertEqual(len(self.package), 16 + glyph_count * 16 + 64 + 24)

    def test_custom_glyphs_use_vdc_sixteen_byte_stride(self):
        glyph_count = self.package[5]
        for index in range(glyph_count):
            start = 16 + index * 16
            self.assertEqual(self.package[start + 8 : start + 16], bytes(8))

    def test_border_codes_name_uploaded_custom_glyphs(self):
        glyph_count = self.package[5]
        for code in self.package[10:16]:
            self.assertGreaterEqual(code, 0x80)
            self.assertLess(code, 0x80 + glyph_count)


if __name__ == "__main__":
    unittest.main()

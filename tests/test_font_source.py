# SPDX-License-Identifier: GPL-3.0-or-later

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FontSourceTests(unittest.TestCase):
    def test_font_defines_digits_and_uppercase_glyphs(self):
        source = (ROOT / "src/services/framebuffer/font.c").read_text(
            encoding="utf-8"
        )
        comments = re.findall(r"/\* ([0-9A-Z]) \*/", source)
        self.assertEqual(comments[:10], list("0123456789"))
        self.assertEqual(comments[10:], list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))

    def test_font_is_five_by_seven_in_eight_pixel_cell(self):
        header = (ROOT / "include/udeks/font.h").read_text(encoding="utf-8")
        self.assertIn("UDEKS_FONT_WIDTH      5u", header)
        self.assertIn("UDEKS_FONT_HEIGHT     7u", header)
        self.assertIn("UDEKS_FONT_CELL_WIDTH 8u", header)
        self.assertIn("UDEKS_FONT_CELL_HEIGHT 8u", header)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from png_to_vic_sprite import read_png_rgb, sprite_bytes


class PngToVicSpriteTests(unittest.TestCase):
    def test_pipe_asset_converts_to_stable_hires_sprite(self):
        source = (ROOT / "assets/24x21-pipe-sprite.png").read_bytes()
        width, height, rgb = read_png_rgb(source)
        sprite = sprite_bytes(width, height, rgb)
        self.assertEqual((width, height), (1341, 1173))
        self.assertEqual(len(sprite), 63)
        self.assertEqual(sum(value.bit_count() for value in sprite), 85)
        self.assertEqual(
            hashlib.sha256(sprite).hexdigest(),
            "df5e16bb2f712aa3ff0680df0c95143955edc14ad74e7aeaab9d72d4ea918c92",
        )

    def test_rejects_mismatched_rgb_raster(self):
        with self.assertRaisesRegex(ValueError, "raster size"):
            sprite_bytes(24, 21, b"short")


if __name__ == "__main__":
    unittest.main()

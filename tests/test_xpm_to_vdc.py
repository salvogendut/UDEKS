# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from xpm_to_vdc import pack_vdc, parse_xpm


TINY_XPM = r'''/* XPM */
static char *tiny[] = {
"8 2 2 1",
"X c #000000",
". c #ffffff",
"X......X",
".XXXXXX."
};
'''


class XpmToVdcTests(unittest.TestCase):
    def test_packs_dark_pixels_msb_first(self):
        image = parse_xpm(TINY_XPM)
        self.assertEqual((image.width, image.height), (8, 2))
        self.assertEqual(pack_vdc(image), bytes((0x81, 0x7E)))

    def test_can_invert_foreground(self):
        self.assertEqual(pack_vdc(parse_xpm(TINY_XPM), False), bytes((0x7E, 0x81)))

    def test_project_splash_is_stable_and_vdc_sized(self):
        image = parse_xpm(
            (ROOT / "assets" / "udekspipe-64.xpm").read_text(encoding="ascii")
        )
        packed = pack_vdc(image)
        self.assertEqual((image.width, image.height), (64, 64))
        self.assertEqual(len(packed), 512)
        self.assertEqual(
            hashlib.sha256(packed).hexdigest(),
            "310c1f047fcaa8485707609e3a40678c594ebd0bbf5149fe185e7b4c065f98bc",
        )

    def test_larger_pipe_variant_is_stable_and_vdc_sized(self):
        image = parse_xpm(
            (ROOT / "assets" / "udekspipe-160.xpm").read_text(encoding="ascii")
        )
        packed = pack_vdc(image)
        self.assertEqual((image.width, image.height), (160, 160))
        self.assertEqual(len(packed), 3200)
        self.assertEqual(
            hashlib.sha256(packed).hexdigest(),
            "fd9a48e23bee4b7e58c9c6c5de40120bcf9c27dfdecdbbfb7c94a64d79aec6f6",
        )

    def test_rejects_more_than_two_colours(self):
        source = TINY_XPM.replace('"8 2 2 1"', '"8 2 3 1"').replace(
            '"X c #000000",', '"X c #000000",\n"+ c #ff0000",'
        )
        with self.assertRaisesRegex(ValueError, "two-colour"):
            parse_xpm(source)


if __name__ == "__main__":
    unittest.main()

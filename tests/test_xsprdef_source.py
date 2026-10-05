# SPDX-License-Identifier: GPL-3.0-or-later
"""XSPRDEF session sprite editor: source, packaging and retained-budget checks."""
import math
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/"user/bin/xsprdef.c"


def sprite_from_rows(rows):
    sprite = bytearray(63)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                sprite[y * 3 + (x >> 3)] |= 0x80 >> (x & 7)
    return bytes(sprite)


def pixel(sprite, x, y):
    return (sprite[y * 3 + (x >> 3)] >> (7 - (x & 7))) & 1


def rectangles(sprite):
    """Host reference of the app's merged-rectangle decomposition."""
    active = []
    out = []
    for y in range(21):
        runs = []
        x = 0
        while x < 24:
            while x < 24 and not pixel(sprite, x, y):
                x += 1
            if x == 24:
                break
            start = x
            while x < 24 and pixel(sprite, x, y):
                x += 1
            runs.append((start, x - start))
        used = [False] * len(runs)
        following = []
        for px, pw, py in active:
            match = next((i for i, (rx, rw) in enumerate(runs)
                          if not used[i] and rx == px and rw == pw), None)
            if match is None:
                out.append((px, py, pw, y - py))
            else:
                used[match] = True
                following.append((px, pw, py))
        following.extend((rx, rw, y) for i, (rx, rw) in enumerate(runs) if not used[i])
        active = following
    out.extend((px, py, pw, 21 - py) for px, pw, py in active)
    return out


def smiley():
    rows = []
    for y in range(21):
        row = []
        for x in range(24):
            radius = math.hypot(x - 11.5, y - 10.0)
            on = 8.2 <= radius <= 10.2
            on = on or (5 <= x <= 7 and 6 <= y <= 8)
            on = on or (16 <= x <= 18 and 6 <= y <= 8)
            mouth = math.hypot(x - 11.5, y - 5.0)
            on = on or (5.5 <= mouth <= 7.0 and y >= 13)
            row.append("#" if on else ".")
        rows.append("".join(row))
    return sprite_from_rows(rows)


class XsprdefSourceTests(unittest.TestCase):
    def test_application_is_a_click_only_session_sprite_editor(self):
        source = SOURCE.read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("unsigned char udeks_graphical_main(void)", source)
        self.assertIn("static unsigned char sprite_bank[SPRITES][SPRITE_BYTES];", source)
        self.assertIn("#define SPRITES      8", source)
        self.assertIn("#define SPRITE_BYTES 63", source)
        self.assertIn("#define CELL         8", source)
        self.assertIn("bit_flip(edit,", source)
        self.assertIn("emit_sprite(edit, MAG_X, MAG_Y, CELL);", source)
        self.assertIn("emit_sprite(edit, PRE_X, PRE_Y, 1);", source)
        self.assertIn("box((unsigned char)(PRE_X - 2u), (unsigned char)(PRE_Y - 2u), 28, 25);", source)
        self.assertIn("box(bx, LIST_Y, 20, 20);", source)
        self.assertIn('P[7 + i] = "XSPRDEF"[i];', source)
        self.assertIn("copy_sprite(sprite_bank[selected], edit);", source)
        self.assertNotIn("udeks_window_", source)
        self.assertNotIn("keyboard", source)
        self.assertIn("user/bin/xsprdef.c", makefile)

    def test_window_geometry_fits_the_create_byte_fields(self):
        source = SOURCE.read_text(encoding="utf-8")
        width = int(re.search(r"P\[4\] = (\d+);", source).group(1))
        height = int(re.search(r"P\[5\] = (\d+);", source).group(1))
        # CREATE carries width/height as single bytes; 320 truncated to 64 once.
        self.assertLessEqual(width, 255)
        self.assertGreaterEqual(width, 24 * 8 + 8 + 24 + 8)
        self.assertLessEqual(height, 200 - 4)
        self.assertGreaterEqual(height, 21 * 8 + 24)

    def test_makefile_builds_and_ships_the_app(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("USER_XSPRDEF_UDEX := $(BUILD_USER)/xsprdef.udx", makefile)
        self.assertIn("--name XSPRDEF", makefile)
        self.assertIn("--static-locals --capacity 4352", makefile)
        self.assertIn("--xsprdef $(USER_XSPRDEF_UDEX)", makefile)
        self.assertIn("$(USER_XSPRDEF_UDEX) $(USER_COWSAY_UDEX)", makefile)

    def test_disk_builder_validates_and_installs_the_editor(self):
        builder = (ROOT / "tools/build_d71.py").read_text(encoding="utf-8")
        self.assertIn("xsprdef: bytes = b\"\"", builder)
        self.assertIn("validate_native_app(xsprdef)", builder)
        self.assertIn('install_prg_file(image, "XSPRDEF.BIN", xsprdef', builder)
        self.assertIn("'XSPRDEF'", builder)
        self.assertIn('parser.add_argument("--xsprdef"', builder)
        self.assertIn("args.xsprdef.read_bytes()", builder)

    def test_retained_command_cap_matches_the_editor_budget(self):
        header = (ROOT / "include/udeks/retained_paths.h").read_text(encoding="utf-8")
        service = (ROOT / "src/services/window/retained_paths.c").read_text(encoding="utf-8")
        self.assertIn("#define UDEKS_RETAINED_COMMANDS 160u", header)
        self.assertIn("length>UDEKS_RETAINED_COMMANDS", service)
        self.assertNotIn("length>48", service)
        self.assertIn("at most 160 eight-byte commands", (ROOT / "abi/window.md").read_text(
            encoding="utf-8"))

    def test_reference_decomposition_fits_the_editor_buffer(self):
        editor = rectangles(smiley())
        self.assertEqual(len(editor), 28)
        source = SOURCE.read_text(encoding="utf-8")
        limit = int(source.split("#define MAX_COMMANDS ", 1)[1].split("\n", 1)[0])
        # One editor image holds the magnified pane, the framed preview and
        # the save confirmation text (or the framed save/back buttons).
        self.assertLessEqual(len(editor) * 2 + 7, limit)


if __name__ == "__main__":
    unittest.main()

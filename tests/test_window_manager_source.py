# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowManagerSourceTests(unittest.TestCase):
    def test_registry_is_bounded_and_tracks_policy_state(self):
        header = (ROOT / "include/udeks/window.h").read_text(encoding="utf-8")
        source = (ROOT / "src/services/window/window_manager.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("#define UDEKS_WINDOW_MAX                  4u", header)
        self.assertIn("struct udeks_window", source)
        for field in ("owner", "surface", "flags", "width", "height", "z"):
            self.assertIn(field, source)
        self.assertIn("top_window_at", source)
        self.assertIn("focused_handle", source)

    def test_manager_owns_chrome_clipping_and_pointer_routing(self):
        source = (ROOT / "src/services/window/window_manager.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("draw_chrome", source)
        self.assertIn("draw_title", source)
        self.assertIn("close_hit", source)
        self.assertIn("title_hit", source)
        self.assertIn("udeks_vic_bitmap_set_clip", source)
        self.assertIn("udeks_pointer_buttons()", source)

    def test_drag_hides_content_moves_outline_and_repaints_on_release(self):
        source = (ROOT / "src/services/window/window_manager.c").read_text(
            encoding="utf-8"
        )
        begin = source.split("static void begin_drag", 1)[1].split(
            "static void move_drag", 1
        )[0]
        move = source.split("static void move_drag", 1)[1].split(
            "static void finish_drag", 1
        )[0]
        finish = source.split("static void finish_drag", 1)[1].split(
            "unsigned char udeks_window_manager_start", 1
        )[0]
        self.assertLess(begin.index("clear_window(window)"), begin.index("udeks_vic_bitmap_outline_toggle"))
        self.assertEqual(move.count("udeks_vic_bitmap_outline_move"), 1)
        self.assertNotIn("paint_window", move)
        self.assertLess(finish.index("udeks_vic_bitmap_outline_toggle"), finish.index("paint_window(handle)"))

    def test_manager_is_an_independent_registered_module(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        descriptor = (ROOT / "src/services/window/descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertIn("_udeks_window_service_descriptor", table)
        self.assertIn(".byte $09, $00", descriptor)
        self.assertIn(".addr _udeks_window_manager_poll", descriptor)


if __name__ == "__main__":
    unittest.main()

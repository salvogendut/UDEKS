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
        self.assertIn("resize_hit", source)
        self.assertIn("UDEKS_WINDOW_FLAG_RESIZABLE", source)
        self.assertIn("udeks_vic_bitmap_set_clip", source)
        self.assertIn("udeks_pointer_buttons()", source)

    def test_drag_recomposes_underlay_moves_outline_and_repaints_on_release(self):
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
        self.assertLess(
            begin.index("compose_damage(handle)"),
            begin.index("udeks_vic_bitmap_outline_toggle"),
        )
        self.assertEqual(move.count("udeks_vic_bitmap_outline_move"), 1)
        self.assertNotIn("compose_damage", move)
        self.assertLess(
            finish.index("udeks_vic_bitmap_outline_toggle"),
            finish.index("compose_damage(UDEKS_WINDOW_NONE)"),
        )

    def test_lower_right_grip_resizes_with_outline_only_until_release(self):
        source = (ROOT / "src/services/window/window_manager.c").read_text(
            encoding="utf-8"
        )
        resize = source.split("static void resize_drag", 1)[1].split(
            "static void finish_drag", 1
        )[0]
        self.assertIn("right - 6, bottom, right, bottom - 6", source)
        self.assertIn("DRAG_RESIZE", source)
        self.assertIn("MINIMUM_WIDTH", resize)
        self.assertIn("MINIMUM_HEIGHT", resize)
        self.assertEqual(resize.count("udeks_vic_bitmap_outline_toggle"), 2)
        self.assertNotIn("compose_damage", resize)
        self.assertIn("window->width = drag_width", source)
        self.assertIn("window->height = drag_height", source)

    def test_damage_is_recomposed_back_to_front_with_normalized_z_order(self):
        source = (ROOT / "src/services/window/window_manager.c").read_text(
            encoding="utf-8"
        )
        compose = source.split("static void compose_damage", 1)[1].split(
            "static unsigned char top_window", 1
        )[0]
        raise_window = source.split("static unsigned char raise_window", 1)[1].split(
            "static unsigned char top_window_at", 1
        )[0]
        self.assertIn("for (rank = 1u; rank <= active_count; ++rank)", compose)
        self.assertIn("paint_window_damage", compose)
        self.assertIn("compose_damage(UDEKS_WINDOW_NONE)", source)
        self.assertIn("--windows[index].z", raise_window)
        self.assertIn("window->z = active_count", raise_window)
        self.assertNotIn("next_z", source)

    def test_incremental_paint_is_limited_to_the_top_window(self):
        source = (ROOT / "src/services/window/window_manager.c").read_text(
            encoding="utf-8"
        )
        begin_paint = source.split("unsigned char udeks_window_begin_paint", 1)[1].split(
            "void udeks_window_end_paint", 1
        )[0]
        self.assertIn("window->z != active_count", begin_paint)
        self.assertIn("dragging_handle != UDEKS_WINDOW_NONE", begin_paint)

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

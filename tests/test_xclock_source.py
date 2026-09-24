# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class XclockSourceTests(unittest.TestCase):
    def test_clock_uses_service_apis_and_fixed_point_geometry(self):
        source = (ROOT / "src/apps/xclock.c").read_text(encoding="utf-8")
        self.assertIn('#include "udeks/time.h"', source)
        self.assertIn('#include "udeks/vic_graphics.h"', source)
        self.assertIn('#include "udeks/window.h"', source)
        self.assertIn("sin64[60]", source)
        self.assertIn("cos64[60]", source)
        self.assertIn("draw_face()", source)
        self.assertIn("draw_hands(", source)
        self.assertIn("draw_digital(", source)
        self.assertNotIn("z80", source.lower())

    def test_clock_is_a_managed_window_with_overlap_safe_ticks(self):
        source = (ROOT / "src/apps/xclock.c").read_text(encoding="utf-8")
        self.assertIn("udeks_window_create(", source)
        self.assertIn("UDEKS_WINDOW_FLAG_MOVABLE", source)
        self.assertIn("UDEKS_WINDOW_FLAG_CLOSABLE", source)
        self.assertIn("paint_clock, close_clock", source)
        self.assertIn("udeks_window_repaint(window_handle)", source)
        self.assertNotIn("udeks_pointer_buttons()", source)
        self.assertNotIn("draw_frame", source)
        self.assertIn("previous_second", source)
        self.assertIn("UDEKS_VIC_COLOR_YELLOW", source)
        self.assertNotIn("udeks_vic_bitmap_commit()", source)

    def test_control_c_is_consumed_by_terminal_job_control(self):
        terminal = (ROOT / "src/services/terminal/root_terminal.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("event.character == 3u", terminal)
        self.assertIn("udeks_xclock_is_running()", terminal)
        self.assertIn("udeks_xclock_stop()", terminal)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RootConsoleSourceTests(unittest.TestCase):
    def test_model_retains_complete_root_console_grid(self):
        header = (ROOT / "include/udeks/root_console.h").read_text(
            encoding="utf-8"
        )
        source = (ROOT / "src/services/window/root_console.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("UDEKS_ROOT_CONSOLE_COLUMNS     64u", header)
        self.assertIn("UDEKS_ROOT_CONSOLE_ROWS        21u", header)
        self.assertIn("UDEKS_ROOT_CONSOLE_ROW_STRIDE  65u", header)
        self.assertIn("cells\n    [UDEKS_ROOT_CONSOLE_ROWS]", source)
        self.assertIn("udeks_root_console_write_at", source)
        self.assertIn("udeks_root_console_put", source)
        self.assertIn("udeks_root_console_set_cursor", source)
        self.assertIn("udeks_root_console_write", source)
        self.assertIn("udeks_root_console_write_string", source)
        self.assertIn("udeks_root_console_row_dirty", source)
        self.assertIn("udeks_root_console_dirty_span", source)
        self.assertIn("dirty_first", source)
        self.assertIn("dirty_last", source)
        self.assertIn("scroll_up", source)
        self.assertIn('#pragma bss-name(push, "LOWBSS")', source)
        self.assertIn('#pragma bss-name(pop)', source)

    def test_boot_messages_populate_model_outside_renderer(self):
        boot = (ROOT / "src/services/window/boot_console.c").read_text(
            encoding="utf-8"
        )
        renderer = (
            ROOT / "src/services/framebuffer/vdc_framebuffer.c"
        ).read_text(encoding="utf-8")
        self.assertIn("udeks_root_console_reset()", boot)
        self.assertIn("udeks_root_console_write_at", boot)
        self.assertIn("udeks_root_console_set_cursor(9, 20, 1)", boot)
        self.assertNotIn("text_title", renderer)
        self.assertNotIn("text_prompt", renderer)

    def test_vdc_renderer_consumes_retained_rows_and_cursor(self):
        renderer = (
            ROOT / "src/services/console/vdc_console.c"
        ).read_text(encoding="utf-8")
        self.assertIn("udeks_boot_console_build()", renderer)
        self.assertIn("udeks_root_console_row(row)", renderer)
        self.assertIn("udeks_root_console_cursor_visible()", renderer)
        self.assertIn("udeks_console_refresh_root", renderer)
        self.assertIn("udeks_root_console_mark_row_clean", renderer)
        self.assertIn("VDC_REG_CURSOR_HI", renderer)

    def test_vdc_logo_rail_lists_only_currently_running_apps(self):
        renderer = (ROOT / "src/services/console/app_panel.s").read_text(
            encoding="utf-8"
        )
        descriptor = (
            ROOT / "src/services/console/descriptor.s"
        ).read_text(encoding="utf-8")
        self.assertIn("_udeks_console_app_panel_initialize", renderer)
        self.assertIn("_udeks_console_poll", renderer)
        for name in ("panel_xinit", "panel_xclock", "panel_xwave"):
            self.assertIn(name + ":", renderer)
        self.assertIn("cmp APP_MASK", renderer)
        self.assertIn(".addr _udeks_console_poll", descriptor)

    def test_vdc_renderer_preserves_mixed_case_with_alternate_charset(self):
        renderer = (
            ROOT / "src/services/console/vdc_console.c"
        ).read_text(encoding="utf-8")
        self.assertIn("SCREEN_ATTRIBUTE_ALT", renderer)
        self.assertIn("attribute_buffer", renderer)
        self.assertIn("source[first + column] >= 'a'", renderer)
        self.assertIn("ATTRIBUTE_BASE +", renderer)

    def test_model_is_linked_into_production_and_panic_images(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertGreaterEqual(makefile.count("root_console.o"), 2)
        self.assertGreaterEqual(makefile.count("boot_console.o"), 2)


if __name__ == "__main__":
    unittest.main()

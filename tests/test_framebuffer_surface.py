# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FramebufferSurfaceTests(unittest.TestCase):
    def test_public_api_exposes_owned_graphics_operations(self):
        header = (ROOT / "include/udeks/framebuffer.h").read_text(
            encoding="utf-8"
        )
        for symbol in (
            "udeks_framebuffer_acquire",
            "udeks_framebuffer_release",
            "udeks_framebuffer_plot",
            "udeks_framebuffer_hline",
            "udeks_framebuffer_fill_rect",
            "udeks_framebuffer_draw_char",
            "udeks_framebuffer_draw_text",
            "udeks_framebuffer_flush",
        ):
            self.assertIn(symbol, header)

    def test_surface_owns_full_backing_store_and_dirty_spans(self):
        source = (ROOT / "src/services/framebuffer/surface.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("pixels[UDEKS_FRAMEBUFFER_SIZE]", source)
        self.assertIn("dirty_map[DIRTY_MAP_SIZE]", source)
        self.assertIn("DIRTY_MAP_STRIDE", source)
        self.assertIn("mark_dirty", source)
        self.assertIn("640u - x", source)
        self.assertIn("x <= 632u", source)
        self.assertNotIn("0xd600", source.lower())
        self.assertNotIn("0xd601", source.lower())

    def test_vdc_owner_flushes_and_verifies_surface_bytes(self):
        source = (ROOT / "src/services/framebuffer/vdc_framebuffer.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("flush_surface()", source)
        self.assertIn("udeks_surface_dirty_span", source)
        self.assertIn("udeks_surface_byte", source)
        self.assertIn("value != udeks_surface_byte(vdc_address)", source)
        self.assertIn("UDEKS_FRAMEBUFFER_API_FLAGS", source)

    def test_surface_is_linked_into_production_and_panic_images(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertGreaterEqual(makefile.count("framebuffer_surface.o"), 2)


if __name__ == "__main__":
    unittest.main()

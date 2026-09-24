# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class XwaveSourceTests(unittest.TestCase):
    def test_application_is_a_managed_resizable_wireframe_plot(self):
        source = (ROOT / "src/apps/xwave.c").read_text(encoding="utf-8")
        self.assertIn('code-name(push, "APP2CODE")', source)
        self.assertIn('rodata-name(push, "APP2RODATA")', source)
        self.assertIn('bss-name(push, "APP2BSS")', source)
        self.assertIn("udeks_window_create(", source)
        self.assertIn("paint_wave, close_wave", source)
        self.assertIn("udeks_window_get_geometry(", source)
        self.assertIn("udeks_vic_bitmap_line(", source)
        self.assertIn("udeks_window_is_dragging(window_handle)", source)
        self.assertIn("udeks_window_is_focused(window_handle)", source)

    def test_computation_uses_bounded_z80_batches_and_8502_fallback(self):
        source = (ROOT / "src/apps/xwave.c").read_text(encoding="utf-8")
        self.assertIn("UDEKS_MB_OP_WAVE_SAMPLES", source)
        self.assertIn("UDEKS_WAVE_BUFFER_SIZE", source)
        self.assertIn("#define PLOT_SAMPLES   64u", source)
        self.assertIn("udeks_z80_submit(", source)
        self.assertIn("sine64[phase >> 2]", source)
        self.assertIn("remaining > UDEKS_WAVE_BUFFER_SIZE", source)

    def test_polling_never_starts_an_unbounded_periodic_repaint(self):
        source = (ROOT / "src/apps/xwave.c").read_text(encoding="utf-8")
        poll = source.split("unsigned char udeks_xwave_poll", 1)[1].split(
            "unsigned char udeks_xwave_stop", 1
        )[0]
        self.assertNotIn("udeks_window_repaint", poll)
        self.assertNotIn("udeks_z80_submit", poll)

    def test_service_descriptor_is_registered_after_xclock(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        descriptor = (ROOT / "src/apps/xwave_descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            table.index(".addr _udeks_xclock_service_descriptor"),
            table.index(".addr _udeks_xwave_service_descriptor"),
        )
        self.assertIn(".byte $0a, $01", descriptor)
        self.assertIn(".addr _udeks_xwave_initialize", descriptor)
        self.assertIn(".addr _udeks_xwave_poll", descriptor)


if __name__ == "__main__":
    unittest.main()

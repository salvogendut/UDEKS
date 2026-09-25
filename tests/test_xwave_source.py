# SPDX-License-Identifier: GPL-3.0-or-later

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class XwaveSourceTests(unittest.TestCase):
    def test_application_is_a_managed_resizable_wireframe_plot(self):
        source = (ROOT / "src/apps/xwave.c").read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("8502-managed-app2.cfg", makefile)
        self.assertIn("--flags 0x02", makefile)
        self.assertIn("udeks_window_create(", source)
        self.assertIn("paint_wave, close_wave", source)
        self.assertIn("udeks_window_get_geometry(", source)
        self.assertIn("udeks_vic_bitmap_line(", source)
        self.assertIn("udeks_window_is_dragging(window_handle)", source)
        self.assertIn("udeks_window_is_focused(window_handle)", source)
        self.assertIn("surface_cache[SURFACE_SAMPLES]", source)
        self.assertIn("if (refresh_samples != 0)", source)

    def test_computation_uses_bounded_z80_batches_and_8502_fallback(self):
        source = (ROOT / "src/apps/xwave.c").read_text(encoding="utf-8")
        worker = (ROOT / "src/z80/worker.c").read_text(encoding="utf-8")
        self.assertIn("UDEKS_MB_OP_SURFACE_ROWS", source)
        self.assertIn("#define SURFACE_ROWS          21u", source)
        self.assertIn("#define SURFACE_COLUMNS       25u", source)
        self.assertIn("udeks_z80_submit(", source)
        self.assertIn("local_surface_height", source)
        self.assertIn("PREVIOUS_HEIGHT_BYTE", source)
        self.assertIn("PROJECTED_WIDTH", source)
        self.assertIn("column != 0 && (row & 1u) == 0", source)
        self.assertIn("row != 0 && (column & 1u) == 0", source)
        self.assertIn(
            "window_height - UDEKS_WINDOW_TITLE_HEIGHT - 5u", source
        )
        tables = []
        for text in (source, worker):
            match = re.search(
                r"sinc_height\[35\]\s*=\s*\{([^}]*)\}", text, re.DOTALL
            )
            self.assertIsNotNone(match)
            tables.append([int(value) for value in re.findall(r"-?\d+", match.group(1))])
        self.assertEqual(tables[0], tables[1])
        self.assertEqual(len(tables[0]), 35)
        self.assertEqual(tables[0][0], 40)
        self.assertGreater(tables[0][0], tables[0][2])
        self.assertLess(min(tables[0]), 0)

    def test_polling_never_starts_an_unbounded_periodic_repaint(self):
        source = (ROOT / "src/apps/xwave.c").read_text(encoding="utf-8")
        poll = source.split("unsigned char udeks_xwave_poll", 1)[1].split(
            "unsigned char udeks_xwave_stop", 1
        )[0]
        self.assertNotIn("udeks_window_repaint", poll)
        self.assertNotIn("udeks_z80_submit", poll)

    def test_managed_app_service_dispatches_both_standalone_images(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        descriptor = (ROOT / "src/services/app/descriptor.s").read_text(
            encoding="utf-8"
        )
        manager = (ROOT / "src/services/app/managed_apps.s").read_text(
            encoding="utf-8"
        )
        self.assertIn(".addr _udeks_managed_apps_service_descriptor", table)
        self.assertIn(".byte $0a, $00", descriptor)
        self.assertIn("XCLOCK          = $0200", manager)
        self.assertIn("XWAVE           = $1200", manager)
        self.assertIn("MANAGED_LOADER  = $f916", manager)
        self.assertGreaterEqual(manager.count("cmp #$00"), 4)
        self.assertFalse((ROOT / "src/services/app/managed_apps.c").exists())


if __name__ == "__main__":
    unittest.main()

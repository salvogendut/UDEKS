# SPDX-License-Identifier: GPL-3.0-or-later
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from repaint_lane_budget import SOURCE, raster_source, verify_objects
from window_repaint_compact import candidate


class RepaintLaneBudgetTests(unittest.TestCase):
    def test_size_guard_rejects_omitted_backend_and_new_mutable_allocations(self):
        fixture = {'lane': {'segments': {'HIGHBSS': 18, 'BSS': 0, 'DATA': 0, 'ZEROPAGE': 0}},
            'compact': {'segments': {'HIGHBSS': 76}},
            'raster': {'segments': {'HIGHBSS': 76, 'BSS': 0, 'DATA': 0, 'ZEROPAGE': 0},
                'functions': {'_draw_chrome_row': {}, '_lane_raster_step': {}}}}
        verify_objects(fixture)
        for name in ('_draw_chrome_row', '_lane_raster_step'):
            broken = copy.deepcopy(fixture)
            del broken['raster']['functions'][name]
            with self.assertRaisesRegex(ValueError, 'omitted'):
                verify_objects(broken)
        for name in ('BSS', 'DATA', 'ZEROPAGE', 'HIGHBSS'):
            broken = copy.deepcopy(fixture)
            broken['lane']['segments'][name] += 1
            with self.assertRaisesRegex(ValueError, 'budget changed|uncharged'):
                verify_objects(broken)

    def test_generated_source_is_sizing_only_preserves_old_callers_and_retains_private_entry(self):
        source = raster_source(candidate(SOURCE.read_text()))
        self.assertNotIn('static void draw_glyph(', source)
        self.assertNotIn('static void draw_title(', source)
        self.assertIn('for (row = 0; row < window->height; ++row) draw_chrome_row(window, row);', source)
        self.assertIn('unsigned char lane_raster_step(', source)
        self.assertNotIn('static unsigned char lane_raster_step(', source)
        self.assertIn('window->paint(handle);', source)  # Old, unintegrated compatibility path still exists.
        self.assertIn('udeks_lane_validate(&work->ticket)', source)


if __name__ == '__main__':
    unittest.main()

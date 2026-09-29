# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_cache_manager import BASE
from window_cache_occlusion import occluded, clock_measurements
from window_cache_repaint import tiled
from test_window_cache_manager import compile_run


class WindowCacheOcclusionTests(unittest.TestCase):
    def test_all_screen_pixels_match_tiled_composition_and_uncovering(self):
        harness = (ROOT / 'bench/window-cache-manager/occlusion-host.inc').read_text()
        with tempfile.TemporaryDirectory() as directory:
            traces = []
            for name, transform in (('tiled', tiled), ('occlusion', occluded)):
                source = transform(BASE.read_text()).replace(
                    '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))',
                    'test_status[offset]')
                code = '#define UDEKS_CACHE_MANAGER_HOST_TEST\n#define OPTIMIZED '+str(int(name == 'occlusion'))+'\n'
                traces.append(compile_run(Path(directory), name, code+harness.replace('SOURCE', source),
                    (ROOT / 'src/services/window/move_cache_state.c',)))
            self.assertEqual(traces[0], traces[1])

    def test_no_new_state_and_bounded_row_poll_remains(self):
        source = occluded(BASE.read_text())
        self.assertIn('unsigned char budget = 4;', source)
        self.assertIn('cache_phase = 0x82u;', source)
        self.assertIn('cache_phase = UDEKS_CACHE_READY;', source)
        self.assertIn('} else cache_paint_image(cache_owner);', source)
        self.assertNotIn('damage_add(window_by_handle(cache_owner));', source)
        self.assertEqual(source.count('#pragma bss-name'), BASE.read_text().count('#pragma bss-name'))

    def test_clock_decoder_requires_exact_cases_one_acknowledgement_and_nonzero_time(self):
        rows = '\n'.join(f'clock repair {case}: x={x} y={y} frames=100 pages=2 callbacks=1 pixels=OK'
            for case, x, y in ((0, 109, 40), (1, 109, 65), (2, 144, 88)))
        self.assertEqual(len(clock_measurements(rows)), 3)
        for text in (rows.splitlines()[0], rows+rows, rows.replace('callbacks=1', 'callbacks=2'),
                     rows.replace('frames=100', 'frames=0'), rows.replace('y=65', 'y=64')):
            with self.assertRaises(ValueError):
                clock_measurements(text)


if __name__ == '__main__':
    unittest.main()

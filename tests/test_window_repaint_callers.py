# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
import window_repaint_callers as callers


class CallerAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager=(ROOT / 'src/services/window/window_manager_cached.c').read_text()
        cls.window=(ROOT / 'include/udeks/window.h').read_text()
        cls.clock=(ROOT / 'src/apps/xclock.c').read_text()
        cls.wave=(ROOT / 'src/apps/xwave.c').read_text()

    def test_actual_source_graph_and_nonprogressing_painters(self):
        report=callers.source_audit(self.manager,self.window,self.clock,self.wave)
        self.assertEqual(report['synchronous_compositions'],10)
        self.assertEqual(report['paint_callback_calls'],2)
        self.assertEqual(report['damage_set_calls'],7)
        self.assertEqual(report['damage_add_calls'],2)
        self.assertEqual(report['public_paint_statuses'],['OK','INVALID','FULL'])
        self.assertIn('whole prefix loop',report['xwave_callback'])
        for source,term in ((self.manager,'compose_damage(UDEKS_WINDOW_NONE);'),
                            (self.manager,'window->paint(handle);'),
                            (self.manager,'window->x = drag_x;'),
                            (self.window,'typedef void (*udeks_window_paint_fn)'),
                            (self.wave,'while (point_offset < draw_offset)'),
                            (self.clock,'static void paint_clock(unsigned char handle)')):
            with self.subTest(term=term):
                with self.assertRaises(ValueError):callers.source_audit(
                    source.replace(term,'/* changed */'),self.window,self.clock,self.wave)

    def test_window_source_exposes_no_bounded_client_progress_contract(self):
        self.assertNotIn('UDEKS_WINDOW_BUSY',self.window)
        self.assertIn('typedef void (*udeks_window_paint_fn)',self.window)
        self.assertNotIn('repaint_frontend_control',self.manager)
        self.assertNotIn('repaint_frontend_poll',self.manager)
        helper=(ROOT / 'bench/window-repaint-callers/control.c').read_text()
        self.assertIn('struct udeks_repaint_rect rect;',helper)
        self.assertIn('return repaint_frontend_control(op,&rect,lease);',helper)
        self.assertNotIn('window->paint',helper)

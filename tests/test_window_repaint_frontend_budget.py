# SPDX-License-Identifier: GPL-3.0-or-later
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import window_repaint_frontend as frontend


class RepaintFrontendBudgetTests(unittest.TestCase):
    def test_rejects_omitted_code_state_and_inconsistent_charges(self):
        prior = {'objects':{'replacement':{'segments':{'CODE':8133}}}, 'component_budget':{'charged':2013,'new_helper_closure':72}}
        obj = {'segments':{'CODE':8633, 'HIGHBSS':88}, 'functions':{n:{} for n in
            ('_repaint_frontend_allowed', '_repaint_frontend_control', '_repaint_frontend_poll')}}
        report = {'object':obj, 'links':{n:{'code_growth':1154, 'library_delta':72} for n in ('normal','panic')},
            'budget':{'frontend_delta':500, 'new_helper_closure':72, 'charged':2513, 'shortfall':400,'replacement_budget':2113}}
        frontend.verify_budget(report, prior)
        for obj_name, key, value in (('segments','HIGHBSS',89), ('segments','BSS',1), ('segments','ZEROPAGE',1)):
            bad = copy.deepcopy(report);bad['object'][obj_name][key] = value
            with self.assertRaises(ValueError):frontend.verify_budget(bad, prior)
        bad = copy.deepcopy(report);del bad['object']['functions']['_repaint_frontend_poll']
        with self.assertRaises(ValueError):frontend.verify_budget(bad, prior)
        for key in ('frontend_delta','new_helper_closure','charged','shortfall','replacement_budget'):
            bad = copy.deepcopy(report);bad['budget'][key] += 1
            with self.assertRaises(ValueError):frontend.verify_budget(bad, prior)
        bad = copy.deepcopy(report);bad['links']['panic']['code_growth'] += 1
        with self.assertRaises(ValueError):frontend.verify_budget(bad, prior)

    def test_no_poll_drain_callbacks_or_persistent_packet_pointer(self):
        source = (ROOT / 'bench/window-repaint-frontend/frontend.inc').read_text()
        self.assertNotIn('#pragma bss-name', source)
        self.assertNotIn('while (', source)
        self.assertNotIn('->paint(', source)
        self.assertNotIn('cache_step(', source)
        self.assertNotIn('UDEKS_REPAINT_RETAINED;', source)
        self.assertLess(source.index('*output = packet.work;'), source.index('return lane_raster_step(output);'))
        self.assertIn('window->x > UDEKS_VIC_WIDTH - window->width', source)
        self.assertIn('window->y > UDEKS_VIC_HEIGHT - window->height', source)

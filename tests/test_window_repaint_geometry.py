# SPDX-License-Identifier: GPL-3.0-or-later
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
import window_repaint_geometry as geometry
import window_repaint_raster as raster
import window_repaint_scenes as scenes


class GeometryTests(unittest.TestCase):
    def test_source_isolated_no_mutable_allocation_and_offsets_locked(self):
        src=(ROOT / 'bench/window-repaint-geometry/damage.s').read_text()
        self.assertNotIn('.segment "BSS"',src)
        self.assertNotIn('.segment "ZEROPAGE"',src)
        self.assertNotIn('jsr',src)
        for field in ('_damage_left','_damage_top','_damage_right','_damage_bottom'):
            self.assertIn(field,src)
        text=raster.compact_source(raster.SOURCE.read_text())+'\n'+scenes.frontend(
            (ROOT / 'bench/window-repaint-frontend/frontend.inc').read_text())
        new=geometry.candidate(text)
        self.assertIn('void damage_set(const struct udeks_window *window);',new)
        self.assertIn('void damage_add(const struct udeks_window *window);',new)
        self.assertNotIn('static void damage_set(',new)
        self.assertNotIn('static void damage_add(',new)
        for field in ('damage_left','damage_top','damage_right','damage_bottom'):
            self.assertIn(' '+field+';',new)
        with self.assertRaises(ValueError):geometry.candidate(text.replace('static void damage_set(','void damage_set('))

    def test_decoder_rejects_faults_including_uninitialized_bss(self):
        data=bytearray(8096);data[:8]=b'DGEO\x01\x02\0\x64'
        self.assertEqual(geometry.decode(data)['cases'],100)
        for off in range(16):
            bad=copy.copy(data);bad[off]^=1
            with self.subTest(offset=off),self.assertRaises(ValueError):geometry.decode(bad)
        with self.assertRaises(ValueError):geometry.decode(data[:-1])
        self.assertIn('__BSS_SIZE__',(ROOT / 'bench/window-repaint-geometry/startup.s').read_text())

# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from graphics_raster_bench_build import function, raster_unit
from graphics_raster_bench_decode import reference, decode, compare
from graphics_raster_link_audit import segments


class GraphicsRasterBenchTests(unittest.TestCase):
    def test_extracts_only_real_raster_implementation(self):
        source = (ROOT / 'src/services/display/vic_graphics.c').read_text()
        unit = raster_unit(source)
        self.assertIn(function(source, 'udeks_vic_bitmap_line'), unit)
        self.assertIn(function(source, 'udeks_vic_bitmap_fill'), unit)
        self.assertNotIn('udeks_vic_graphics_poll(', unit)
        with self.assertRaises(ValueError):
            function('void broken(void) {', 'broken')
        with self.assertRaises(ValueError):
            raster_unit('')

    def test_decoder_requires_complete_pixels_dirty_map_and_header(self):
        block = bytearray(64) + bytearray(reference(0))
        block[:8] = b'RAST\x01\x02\x00\x00'
        block[8:12] = (100).to_bytes(4, 'little')
        self.assertEqual(decode(block, 0, 0), 100)
        for offset in (0, 5, 6, 7, 12, 64, 8064):
            damaged = block[:]
            damaged[offset] ^= 1
            with self.assertRaises(ValueError):
                decode(damaged, 0, 0)
        block[8:12] = bytes(4)
        with self.assertRaisesRegex(ValueError, 'zero'):
            decode(block, 0, 0)

    def test_current_irq_and_raster_paths_do_not_reenter_or_yield(self):
        irq = (ROOT / 'src/8502/pointer_irq.s').read_text()
        self.assertNotIn('_udeks_vic_bitmap', irq)
        self.assertNotIn('_udeks_service_poll', irq)
        tick = (ROOT / 'src/scheduler/task_wait_state.s').read_text().split(
            '_udeks_task_tick_advance:', 1)[1].split('.segment "BSS"', 1)[0]
        self.assertEqual(set(re.findall(r'\bjsr\s+(\w+)', tick)), {'increment_monotonic'})
        unit = raster_unit((ROOT / 'src/services/display/vic_graphics.c').read_text())
        for name in ('udeks_service_poll', 'udeks_task_yield', 'udeks_window_', 'udeks_z80_submit'):
            self.assertNotIn(name, unit)

    def test_preserved_timing_and_link_evidence(self):
        directory = ROOT / 'bench/results/2026-09-27-graphics-raster-timing'
        report = compare(directory / 'raw')
        self.assertEqual(report, json.loads((directory / 'report.json').read_text()))
        for row in report['cases']:
            for engine in ('1986', 'vice'):
                self.assertGreater(row[engine]['reduction_percent'], 0)
        for kind in ('results', 'artifacts'):
            path = ROOT / 'bench' / kind / '2026-09-27-graphics-raster-timing'
            for line in (path / 'SHA256SUMS').read_text().splitlines():
                digest, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((path / name).read_bytes()).hexdigest(), digest, name)
        link = json.loads((directory / 'link-report.json').read_text())
        self.assertEqual(link['linked_end_reduction'], 49)
        self.assertEqual(link['baseline']['VICSHADOW']['start'], 0xA1E0)
        self.assertEqual(link['static-scratch']['VICSHADOW']['start'], 0xA1AF)
        for name in ('ZEROPAGE', 'SYSCALLS', 'TASKGATE', 'TASKREQUEST'):
            self.assertEqual(link['baseline'][name], link['static-scratch'][name])
        self.assertEqual(segments((directory / 'baseline.map').read_text()), link['baseline'])
        self.assertEqual(segments((directory / 'static-scratch.map').read_text()), link['static-scratch'])

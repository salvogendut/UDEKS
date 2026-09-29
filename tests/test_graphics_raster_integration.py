# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from graphics_raster_bench_decode import compare
from graphics_raster_link_audit import segments

class RasterIntegrationTests(unittest.TestCase):
    def test_preserved_artifact_and_result_hashes(self):
        for kind in ('results', 'artifacts'):
            directory = ROOT / 'bench' / kind / '2026-09-28-graphics-raster-integration'
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                digest, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest, name)

    def test_integrated_pixels_and_frozen_placement(self):
        directory = ROOT / 'bench/results/2026-09-28-graphics-raster-integration'
        self.assertEqual(compare(directory / 'raw'), json.loads((directory / 'report.json').read_text()))
        actual = segments((directory / 'integrated.map').read_text())
        report = json.loads((directory / 'link-report.json').read_text())
        self.assertEqual(actual, report['static-scratch'])
        self.assertEqual(actual['VICSHADOW'], {'start': 0xA1E0, 'end': 0xC11F, 'size': 8000})
        self.assertEqual(actual['BSS']['size'], 702)
        self.assertEqual(report['linked_end_reduction'], 49)
        shadow = (directory / 'raw/shadow-drawn.bin').read_bytes()
        bitmap = (directory / 'raw/vic-bitmap.bin').read_bytes()
        # VICE monitor saves include their distinct two-byte load addresses.
        self.assertEqual(len(shadow), 8002)
        self.assertEqual(len(bitmap), 8002)
        self.assertEqual(shadow[:2], b'\xe0\xa1')
        self.assertEqual(bitmap[:2], b'\x00\x60')
        self.assertEqual(shadow[2:], bitmap[2:])
        snapshot = ROOT / 'bench/artifacts/2026-09-28-graphics-raster-integration/vic_graphics.c'
        object_report = json.loads((directory / 'object-report.json').read_text())
        self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(), object_report['source_sha256'])

    def test_native_stress_evidence_and_latency(self):
        directory = ROOT / 'bench/results/2026-09-28-graphics-raster-integration'
        for name, expected in [('baseline-drag.log', (348, 619, 194)),
                               ('integrated-drag.log', (290, 541, 216)),
                               ('integrated-d64.log', (290, 541, 216))]:
            text = (directory / name).read_text()
            self.assertEqual(len(re.findall(r'^stress \d+:', text, re.M)), 32)
            self.assertIn('PASS: repeated native wave drags and console cancellation', text)
            match = re.search(r'partial=(\d+) cached=(\d+); completed-wave cancellation=(\d+)', text)
            self.assertEqual(tuple(map(int, match.groups())), expected)

if __name__ == '__main__':
    unittest.main()

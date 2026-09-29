# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'bench/artifacts/2026-09-29-repaint-lane'
RESULT = ROOT / 'bench/results/2026-09-29-repaint-lane'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RepaintLaneEvidenceTests(unittest.TestCase):
    def test_measured_entries_and_state_are_charged_without_claiming_integration(self):
        report = json.loads((RESULT / 'budget.json').read_text())
        self.assertIn('not linked closure or poll integration', report['scope'])
        for name, expected in report['input_sha256'].items():
            self.assertEqual(digest(ART / 'inputs' / name), expected, name)
        for name, expected in report['output_sha256'].items():
            self.assertEqual(digest(ART / 'build' / name), expected, name)
        self.assertEqual(report['layout'], {'lane': 18, 'ticket': 6, 'work': 12, 'scene_view': 9})
        self.assertEqual((ART / 'build/layout.bin').read_bytes(), bytes([18, 6, 12, 9]))
        state = report['state_replacement']
        self.assertEqual(state['compact_manager'] - state['old_damage_removed'] + state['lane_added'], 88)
        self.assertEqual(state['total'], state['accepted_manager_total'])
        self.assertIn('old damage globals are still present', state['qualification'])
        self.assertEqual(report['objects']['lane']['segments']['HIGHBSS'], 18)
        self.assertEqual(report['code']['lane'], 2641)
        self.assertEqual(report['code']['optimistic_shortfall'], 3171)
        raster = report['objects']['raster']['functions']
        self.assertEqual(raster['_draw_chrome_row']['size'], 1468)
        self.assertEqual(raster['_lane_raster_step']['size'], 1175)
        self.assertEqual(raster['_draw_chrome']['size'], 70)  # Unintegrated synchronous compatibility loop.
        self.assertEqual(report['code']['row_adapter_delta'], 1401)

    def test_hash_manifests_cover_all_preserved_files(self):
        for directory in (ART, RESULT):
            declared = {}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                declared[name] = sha
                self.assertEqual(digest(directory / name), sha, name)
            self.assertEqual(set(declared), {str(path.relative_to(directory)) for path in directory.rglob('*')
                if path.is_file() and path.name != 'SHA256SUMS'})

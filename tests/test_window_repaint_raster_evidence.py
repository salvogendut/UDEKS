# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import window_repaint_raster as raster

ART = ROOT / 'bench/artifacts/2026-09-29-repaint-raster'
RESULT = ROOT / 'bench/results/2026-09-29-repaint-raster'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RepaintRasterEvidenceTests(unittest.TestCase):
    def test_actual_closure_charges_helpers_and_state_without_claiming_fit(self):
        report = json.loads((RESULT / 'budget.json').read_text())
        self.assertIn('UNBOOTABLE', report['scope'])
        self.assertIn('no poll/provider/delivery integration', report['scope'])
        budget = report['component_budget']
        self.assertEqual([budget[n] for n in ('row_with_helpers', 'backend', 'receipt',
            'binding', 'new_helper_closure', 'old_bodies', 'reserve', 'charged', 'optimistic_headroom')],
            [975, 755, 127, 84, 72, 1976, 137, 2013, 100])
        self.assertIn('excludes real poll/view/admission/provider/busy/teardown costs', budget['scope'])
        raster.verify_components(report['objects'])
        previous = report['objects']['previous']['functions']
        self.assertEqual(previous['_draw_chrome_row']['size'] + previous['_lane_raster_step']['size']
            - budget['row_with_helpers'] - budget['backend'], 913)
        for link in report['links'].values():
            self.assertEqual(link['code_growth'], 654)
            self.assertEqual(link['library_delta'], 72)
            self.assertEqual({s:n for s,n in link['library_segment_delta'].items() if n}, {'CODE':72})
            self.assertEqual({n.split('(')[1].rstrip(')') for n in link['added_helpers']},
                {'memcpy.o', 'return0.o', 'ult.o'})
            self.assertEqual(link['removed_helpers'], [])
            old, new = link['baseline'], link['replacement']
            for name in set(old) - {'CODE', 'RODATA', 'DATA', 'BSS', 'VICSHADOW'}:
                self.assertEqual(old[name], new[name], name)
            for name in ('RODATA', 'DATA', 'BSS', 'VICSHADOW'):
                self.assertEqual(old[name]['size'], new[name]['size'], name)
            self.assertEqual(new['HIGHBSS']['size'], 298)
        self.assertGreater((ART / 'build/none.lib').stat().st_size, 10000)
        for name, sha in report['input_sha256'].items():
            self.assertEqual(digest(ART / 'inputs' / name), sha, name)
        for name, sha in report['output_sha256'].items():
            self.assertEqual(digest(ART / 'build' / name), sha, name)

    def test_both_engines_match_exact_final_pixels_and_the_same_qualified_build(self):
        report = json.loads((RESULT / 'budget.json').read_text())
        self.assertIn('mock row client and memory-only page commit', report['native']['scope'])
        self.assertEqual(digest(ART / 'build/native.prg'), report['native']['native_sha256'])
        for engine in ('1986', 'vice'):
            run = json.loads((RESULT / (engine + '.json')).read_text())
            self.assertEqual(run['build_report_sha256'], digest(RESULT / 'budget.json'))
            self.assertEqual(run['native_sha256'], report['native']['native_sha256'])
            path = RESULT / (engine + '.bin')
            self.assertEqual(digest(path), run['raw_sha256'])
            data = path.read_bytes()
            self.assertEqual(raster.decode(data), run['decoded'])
            self.assertEqual(data[64:8064], (ART / 'build/expected-final.bin').read_bytes())
            self.assertEqual(run['decoded']['scene_checksums'], report['native']['scene_checksums'])
            self.assertEqual(run['decoded']['final_sha256'], report['native']['final_sha256'])
            self.assertTrue(run['provenance'])

    def test_manifests_cover_every_preserved_file(self):
        for directory in (ART, RESULT):
            declared = {}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                self.assertNotIn(name, declared)
                declared[name] = sha
                self.assertEqual(digest(directory / name), sha, name)
            self.assertEqual(set(declared), {str(p.relative_to(directory)) for p in directory.rglob('*')
                if p.is_file() and p != directory / 'SHA256SUMS'})

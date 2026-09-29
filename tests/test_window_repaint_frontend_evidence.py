# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import window_repaint_frontend as frontend
from graphics_raster_link_audit import segments

ART = ROOT / 'bench/artifacts/2026-09-29-repaint-frontend'
RESULT = ROOT / 'bench/results/2026-09-29-repaint-frontend'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RepaintFrontendEvidenceTests(unittest.TestCase):
    def test_full_budget_is_negative_and_does_not_grant_unretired_code(self):
        report = json.loads((RESULT / 'budget.json').read_text())
        prior = json.loads((ART / 'inputs/bench/results/2026-09-29-repaint-raster/budget.json').read_text())
        frontend.verify_budget(report, prior)
        self.assertIn('UNBOOTABLE', report['scope'])
        self.assertIn('not wired to real manager poll/lifecycle', report['scope'])
        self.assertIn('no admission/NMI/provider qualification', report['scope'])
        self.assertEqual({n:report['budget'][n] for n in ('frontend_delta','new_helper_closure','charged','replacement_budget','shortfall')},
            {'frontend_delta':586,'new_helper_closure':72,'charged':2599,'replacement_budget':2113,'shortfall':486})
        self.assertEqual(report['object']['segments']['CODE'], 8719)
        self.assertEqual([report['object']['functions'][n]['size'] for n in
            ('_repaint_frontend_allowed','_repaint_frontend_control','_repaint_frontend_poll')], [48,98,440])
        self.assertIn('NOT granted as free code', report['retirement_scope'])
        self.assertEqual(sum(report['possible_retirements'].values()),722)
        self.assertIn('future admission/paint lease flag/caller costs uncharged', report['state'])
        for name in ('normal','panic'):
            link = report['links'][name]
            self.assertEqual(link['code_growth'],1240)
            self.assertEqual({s:n for s,n in link['library_segment_delta'].items() if n}, {'CODE':72})
            self.assertEqual({n.split('(')[1].rstrip(')') for n in link['added_helpers']},
                {'memcpy.o','return0.o','ult.o'})
            self.assertEqual(link['removed_helpers'],[])
            for variant in ('baseline','replacement'):
                map_path = ART / 'build' / name / variant / 'kernel.map'
                self.assertEqual(segments(map_path.read_text()),link[variant])
            old,new = link['baseline'],link['replacement']
            for segment in set(old) - {'CODE','RODATA','DATA','BSS','VICSHADOW'}:
                self.assertEqual(old[segment],new[segment])
            for segment in ('RODATA','DATA','BSS','VICSHADOW'):
                self.assertEqual(old[segment]['size'],new[segment]['size'])
            self.assertEqual(new['HIGHBSS']['size'],298)

    def test_exact_sources_provider_objects_and_library_are_preserved(self):
        report = json.loads((RESULT / 'budget.json').read_text())
        self.assertGreater((ART / 'build/none.lib').stat().st_size,10000)
        for prefix, entries in (('inputs',report['input_sha256']),('build',report['output_sha256'])):
            for name,sha in entries.items():
                self.assertEqual(digest(ART / prefix / name),sha,name)
        self.assertEqual((ART / 'build/receipt.o').read_bytes(),
            (ART / 'inputs/bench/artifacts/2026-09-29-repaint-raster/build/receipt.o').read_bytes())
        self.assertEqual((ART / 'build/binding.o').read_bytes(),
            (ART / 'inputs/bench/artifacts/2026-09-29-repaint-raster/build/binding.o').read_bytes())

    def test_manifest_covers_all_files_including_nested_manifests(self):
        for directory in (ART,RESULT):
            entries={}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,name=line.split('  ',1)
                self.assertNotIn(name,entries)
                entries[name]=sha
                self.assertEqual(digest(directory / name),sha,name)
            self.assertEqual(set(entries),{str(p.relative_to(directory)) for p in directory.rglob('*')
                if p.is_file() and p!=directory / 'SHA256SUMS'})

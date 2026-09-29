# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
from graphics_raster_link_audit import segments

ART=ROOT / 'bench/artifacts/2026-09-29-repaint-callers'
RESULT=ROOT / 'bench/results/2026-09-29-repaint-callers'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class CallerEvidenceTests(unittest.TestCase):
    def test_measured_marshalling_floor_and_complete_links(self):
        r=json.loads((RESULT / 'budget.json').read_text())
        self.assertIn('UNBOOTABLE',r['scope'])
        self.assertIn('BEFORE a single caller',r['budget']['scope'])
        self.assertEqual(r['object']['segments']['CODE'],78)
        for seg in ('BSS','DATA','HIGHBSS','RODATA','ZEROPAGE'):
            self.assertEqual(r['object']['segments'].get(seg,0),0)
        self.assertEqual(r['budget']['measured_floor'],255)
        self.assertEqual(r['audit']['synchronous_compositions'],10)
        self.assertEqual(r['audit']['paint_callback_calls'],2)
        for name in ('normal','panic'):
            link=r['links'][name]
            self.assertEqual(link['code_delta_over_geometry'],78)
            self.assertEqual(link['code_growth_over_production'],1009)
            self.assertEqual(segments((ART / 'build' / name / 'kernel.map').read_text()),link['segments'])
            self.assertEqual(link['segments']['HIGHBSS']['size'],298)

    def test_inputs_outputs_and_nested_manifests(self):
        r=json.loads((RESULT / 'budget.json').read_text())
        for prefix,items in (('inputs',r['input_sha256']),('build',r['output_sha256'])):
            for n,sha in items.items():self.assertEqual(digest(ART / prefix / n),sha,n)
        for directory in (ART,RESULT):
            entries={}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,n=line.split('  ',1);self.assertNotIn(n,entries);entries[n]=sha
                self.assertEqual(digest(directory / n),sha,n)
            self.assertEqual(set(entries),{str(p.relative_to(directory)) for p in directory.rglob('*')
                if p.is_file() and p!=directory / 'SHA256SUMS'})

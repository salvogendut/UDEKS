# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
import window_repaint_geometry as geometry
from graphics_raster_link_audit import segments

ART=ROOT / 'bench/artifacts/2026-09-29-repaint-geometry'
RESULT=ROOT / 'bench/results/2026-09-29-repaint-geometry'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class GeometryEvidenceTests(unittest.TestCase):
    def test_full_links_charge_all_assembly_and_preserve_fixed_state(self):
        report=json.loads((RESULT / 'budget.json').read_text())
        b=report['budget']
        self.assertIn('UNBOOTABLE',report['scope'])
        self.assertIn('NOT retired',b['scope'])
        self.assertEqual({n:b[n] for n in ('removed_C','asm_CODE','net_object_CODE_saved','full_link_CODE_growth',
            'resident_growth_recovered','provisional_remaining_shortfall')},
            {'removed_C':250,'asm_CODE':169,'net_object_CODE_saved':81,'full_link_CODE_growth':931,
             'resident_growth_recovered':81,'provisional_remaining_shortfall':177})
        self.assertEqual(report['objects']['assembly'].get('HIGHBSS',0),0)
        for name in ('normal','panic'):
            link=report['links'][name]
            self.assertEqual(link['code_growth'],931)
            self.assertEqual({n:v for n,v in link['library_segment_delta'].items() if v},{'CODE':72})
            for variant in ('baseline','replacement'):
                path=ART / 'build' / name / variant / 'kernel.map'
                self.assertEqual(segments(path.read_text()),link[variant])
            old,new=link['baseline'],link['replacement']
            for segment in set(old)-{'CODE','RODATA','DATA','BSS','VICSHADOW'}:
                self.assertEqual(old[segment],new[segment])
            for segment in ('RODATA','DATA','BSS','VICSHADOW'):
                self.assertEqual(old[segment]['size'],new[segment]['size'])

    def test_exact_inputs_outputs_and_both_native_records_are_bound(self):
        report=json.loads((RESULT / 'budget.json').read_text())
        for prefix,paths in (('inputs',report['input_sha256']),('build',report['output_sha256'])):
            for n,sha in paths.items():self.assertEqual(digest(ART / prefix / n),sha,n)
        for engine in ('1986','vice'):
            result=json.loads((RESULT / (engine+'.json')).read_text())
            data=(RESULT / (engine+'.bin')).read_bytes()
            self.assertEqual(geometry.decode(data),result['decoded'])
            self.assertEqual(digest(RESULT / (engine+'.bin')),result['raw_sha256'])
            self.assertEqual(digest(ART / 'build/probe.prg'),result['native_sha256'])
            self.assertEqual(digest(RESULT / 'budget.json'),result['build_report_sha256'])
            self.assertTrue(result['provenance'])
        self.assertEqual((RESULT / '1986.bin').read_bytes()[:16],(RESULT / 'vice.bin').read_bytes()[:16])

    def test_full_manifest_including_nested_prior_manifests(self):
        for directory in (ART,RESULT):
            listed={}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,n=line.split('  ',1);self.assertNotIn(n,listed);listed[n]=sha
                self.assertEqual(digest(directory / n),sha,n)
            self.assertEqual(set(listed),{str(p.relative_to(directory)) for p in directory.rglob('*')
                if p.is_file() and p!=directory / 'SHA256SUMS'})

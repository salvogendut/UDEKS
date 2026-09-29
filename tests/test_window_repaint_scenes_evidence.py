# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
import window_repaint_scenes as scenes
from graphics_raster_link_audit import segments
from placement_audit import parse_map

ART=ROOT / 'bench/artifacts/2026-09-29-repaint-scenes'
RESULT=ROOT / 'bench/results/2026-09-29-repaint-scenes'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class SceneEvidenceTests(unittest.TestCase):
    def test_closures_layout_and_unreclaimed_helpers(self):
        report=json.loads((RESULT / 'budget.json').read_text())
        scenes.verify_budget(report)
        self.assertIn('UNBOOTABLE',report['scope'])
        self.assertIn('NOT retired',report['budget']['scope'])
        self.assertEqual(report['budget']['charged'],2371)
        self.assertEqual(report['budget']['shortfall'],258)
        self.assertEqual(report['budget']['poll_saving'],228)
        self.assertEqual(report['object']['segments']['CODE'],8491)
        for n,size in (('_damage_set',87),('_damage_add',163),('_set_damage_intersection',316),('_cache_paint_image',156)):
            self.assertEqual(report['object']['functions'][n]['size'],size)
        for n in ('normal','panic'):
            link=report['links'][n]
            self.assertEqual(link['code_growth'],1012)
            self.assertEqual({s:v for s,v in link['library_segment_delta'].items() if v},{'CODE':72})
            self.assertEqual(link['removed_helpers'],[])
            for variant in ('baseline','replacement'):
                self.assertEqual(segments((ART / 'build' / n / variant / 'kernel.map').read_text()),link[variant])
            for name in set(link['baseline'])-{'CODE','RODATA','DATA','BSS','VICSHADOW'}:
                self.assertEqual(link['baseline'][name],link['replacement'][name])
            for name in ('RODATA','DATA','BSS','VICSHADOW'):
                self.assertEqual(link['baseline'][name]['size'],link['replacement'][name]['size'])
        module=report['module'];self.assertEqual(module['bytes'],3720)
        self.assertEqual(module['helper_bytes'],512)
        self.assertEqual(sum(s.get('CODE',0) for s in module['helpers'].values()),512)
        self.assertEqual(sum(s.get('ZEROPAGE',0) for s in module['helpers'].values()),26)
        self.assertEqual(module['code_spare'],88)
        self.assertEqual(module['local_view_bytes'],36)
        self.assertEqual(len((ART / 'build/module.bin').read_bytes()),3720)
        _,ranges=parse_map((ART / 'build/module.map').read_text())
        self.assertEqual({n:[s,e] for n,s,e in ranges},module['segments'])
        for n in ('layout-resident','layout-native'):
            self.assertEqual((ART / 'build' / (n+'.bin')).read_bytes(),scenes.LAYOUT)
        for n,key in (('layout-bad-prefix','negative_prefix'),('layout-bad-packet','negative_packet')):
            self.assertEqual(list((ART / 'build' / (n+'.bin')).read_bytes()),report['layout'][key])
            self.assertNotEqual((ART / 'build' / (n+'.bin')).read_bytes(),scenes.LAYOUT)

    def test_hash_bound_runs_and_full_source_provider_archives(self):
        report=json.loads((RESULT / 'budget.json').read_text())
        for prefix,entries in (('inputs',report['input_sha256']),('build',report['output_sha256'])):
            for name,sha in entries.items():self.assertEqual(digest(ART / prefix / name),sha,name)
        for n in ('none.lib','bank-none.lib'):self.assertGreater((ART / 'build' / n).stat().st_size,10000)
        for engine in ('1986','vice'):
            run=json.loads((RESULT / (engine+'.json')).read_text())
            data=(RESULT / (engine+'.bin')).read_bytes()
            self.assertEqual(digest(RESULT / (engine+'.bin')),run['raw_sha256'])
            self.assertEqual(digest(RESULT / 'budget.json'),run['build_report_sha256'])
            self.assertEqual(digest(ART / 'build/native.prg'),run['native_sha256'])
            self.assertEqual(scenes.decode(data),run['decoded'])
            self.assertEqual(run['decoded']['lowest_changed_stack_offset'],169)
            self.assertEqual(run['decoded']['protocol_rejections'],4)
            self.assertIn('mock',report['native']['scope'])
            self.assertTrue(run['provenance'])

    def test_all_files_including_nested_manifests_are_sealed(self):
        for directory in (ART,RESULT):
            entries={}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,name=line.split('  ',1)
                self.assertNotIn(name,entries);entries[name]=sha
                self.assertEqual(digest(directory / name),sha,name)
            self.assertEqual(set(entries),{str(p.relative_to(directory)) for p in directory.rglob('*')
                if p.is_file() and p!=directory / 'SHA256SUMS'})

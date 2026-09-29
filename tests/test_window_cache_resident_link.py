# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_cache_resident_link import NAME, spend_padding, retarget_config
from graphics_raster_link_audit import segments


class WindowCacheResidentLinkTests(unittest.TestCase):
    def test_padding_is_exactly_charged_and_other_reservations_untouched(self):
        source = (ROOT / 'src/8502/vic_graphics.s').read_text()
        candidate = spend_padding(source)
        self.assertIn('raster_primitives_placement_reserve:\n        .res 131, $ea', candidate)
        self.assertEqual(candidate.count('.res 0, $ea'), source.count('.res 0, $ea')+2)
        with self.assertRaises(ValueError): spend_padding(source.replace('.res 280, $ea', '.res 279, $ea'))
        config = retarget_config((ROOT / 'cfg/8502-bootstrap.cfg').read_text(), Path('/tmp/cache-link'))
        self.assertNotIn('file = "build/', config)
        self.assertIn('file = %O', config)

    def test_real_normal_panic_links_preserve_every_segment_and_runtime_helper(self):
        artifact = ROOT / 'bench/artifacts' / NAME
        report = json.loads((artifact / 'build/report.json').read_text())
        self.assertIn('UNBOOTABLE', report['qualification'])
        self.assertEqual((report['charged_bytes'], report['remaining_before_hooks']), (371, 131))
        self.assertEqual([report['objects'][n]['CODE'] for n in ('raw', 'binding', 'helper')], [51,309,11])
        for name in ('raw','binding','helper'):
            for segment in ('BSS','DATA','ZEROPAGE','RODATA'):
                self.assertEqual(report['objects'][name][segment], 0)
        self.assertEqual(set(report['links']), {'normal','panic'})
        for label, link in report['links'].items():
            self.assertEqual(link['segments'], link['baseline_segments'])
            self.assertEqual(link['segments'], segments((artifact / 'build' / label / 'kernel.map').read_text()))
            self.assertEqual(link['helpers'], link['baseline_helpers'])
            self.assertEqual(link['segments']['VICSHADOW'], {'start':0xa1e0,'end':0xc11f,'size':8000})
            self.assertEqual(link['remaining_padding'], 131)
            fields = link['fields']
            base = fields['_cache_accept_state'][0]
            self.assertEqual({n:v[0]-base for n,v in fields.items()},
                {'_cache_accept_state':0,'_cache_ticket':1,'_cache_owner':3,'_cache_phase':4})
            for address, kind in fields.values():
                self.assertEqual(kind, 'RLA')
                self.assertTrue(link['segments']['CODE']['start'] <= address <= link['segments']['CODE']['end'])

    def test_archive_binds_actual_provider_objects_generated_inputs_and_split_outputs(self):
        artifact = ROOT / 'bench/artifacts' / NAME
        report = json.loads((artifact / 'build/report.json').read_text())
        for key, root in (('inputs_sha256',artifact), ('outputs_sha256',artifact / 'build')):
            for name, sha in report[key].items():
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), sha, name)
        for label in ('normal','panic'):
            self.assertIn(label+'/udeks-module.bin', report['outputs_sha256'])
            self.assertIn(label+'/bootfs-request-service.bin', report['outputs_sha256'])
            self.assertIn(label+'/task-request-gateway.bin', report['outputs_sha256'])
            self.assertIn(label+'/task-bank-gateway.bin', report['outputs_sha256'])
        for line in (artifact / 'SHA256SUMS').read_text().splitlines():
            sha, name = line.split('  ',1)
            self.assertEqual(hashlib.sha256((artifact / name).read_bytes()).hexdigest(), sha, name)

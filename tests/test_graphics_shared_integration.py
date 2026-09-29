# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
from graphics_primitives_qualify import SHARED_NAME, SHARED_DISKS, validate_layout, stress_result
from graphics_raster_bench_build import function

ARTIFACTS = ROOT / 'bench/artifacts' / SHARED_NAME
RESULTS = ROOT / 'bench/results' / SHARED_NAME


class GraphicsSharedIntegrationTests(unittest.TestCase):
    def test_current_service_matches_qualified_candidates(self):
        source=(ROOT / 'src/services/display/vic_graphics.c').read_text()
        for name in ('line','rectangle'):
            self.assertEqual(function(source,'udeks_vic_bitmap_'+name),
                function((ROOT / 'bench/graphics-shared' / (name+'.c')).read_text(),'udeks_vic_bitmap_'+name))
        self.assertNotIn('void udeks_vic_bitmap_clear(',source)
        self.assertEqual((ROOT / 'src/services/display/vic_clear.s').read_bytes(),
                         (ROOT / 'bench/graphics-shared/clear.s').read_bytes())

    def test_installed_layout_and_growth_guards(self):
        normal=(ARTIFACTS / 'build/8502/udeks-8502.map').read_text()
        panic=(ARTIFACTS / 'build/8502/udeks-8502-panic-probe.map').read_text()
        dump=(RESULTS / 'gateway-exports.txt').read_text()
        result=validate_layout(normal,panic,dump,shared=True)
        report=json.loads((RESULTS / 'qualification.json').read_text())
        for key,value in result.items():self.assertEqual(report[key],value)
        self.assertEqual(result['net_saved'],467)
        self.assertEqual(result['display_code'],3797)
        self.assertEqual(result['display_bss'],26)
        for broken in (normal.replace('00A1E0','00A1E1'),
                       re.sub(r'(vic_clear.o:\n[^\n]*Size=)000034',r'\g<1>000035',normal),
                       re.sub(r'(\bsp\s+)000006(\s+RLZ)',r'\g<1>000007\2',normal)):
            self.assertNotEqual(broken,normal)
            with self.assertRaises(ValueError):validate_layout(broken,broken,dump,shared=True)
        with self.assertRaises(ValueError):validate_layout(normal,panic,dump)

    def test_native_metrics_keep_cancellation_regression_visible(self):
        report=json.loads((RESULTS / 'qualification.json').read_text())
        for label in ('baseline','d71','d64'):
            text=(RESULTS / f'build/shared-{label}.log').read_text()
            self.assertEqual(stress_result(text),report['native'][label])
        self.assertEqual(report['native']['d71'],report['native']['d64'])
        self.assertEqual(report['native']['d71']['partial'],107)
        self.assertEqual(report['native']['d71']['cached'],103)
        self.assertEqual(report['native']['d71']['remaining_replay'],655)
        self.assertEqual(report['native']['baseline']['cancellation'],140)
        self.assertEqual(report['native']['d71']['cancellation'],161)
        self.assertIn('pending',report['physical_hardware'])
        self.assertIn('not installed',report['pixel_cache'])

    def test_padding_budget_does_not_claim_guard_or_scheduler_space(self):
        report=json.loads((RESULTS / 'build/graphics-cache-placement/report.json').read_text())
        self.assertEqual(report['candidate']['qualified_reserve'],516)
        self.assertEqual(report['candidate']['additional_bytes_before_bindings'],507)
        self.assertEqual(report['primitive_placement_padding'],173)
        self.assertEqual(report['shared_placement_padding'],294)
        self.assertEqual(report['integrated_primitives']['clear'],{'CODE':52})
        self.assertEqual(report['post_shadow']['unowned_bytes'],0)
        self.assertTrue(all(not row['available_to_cache'] for row in report['other_regions']))

    def test_preserved_disks_bitmap_payload_and_hashes(self):
        directory=RESULTS / 'build/vice/shared-shadow'
        shadow=(directory / 'shadow-drawn.bin').read_bytes()
        self.assertEqual(len(shadow),8000)
        self.assertEqual(shadow,(directory / 'vic-bitmap.bin').read_bytes())
        for name,sha in SHARED_DISKS.items():
            self.assertEqual(hashlib.sha256((ARTIFACTS / 'build/boot' / name).read_bytes()).hexdigest(),sha)
        for directory in (ARTIFACTS,RESULTS):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,name=line.split('  ',1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)

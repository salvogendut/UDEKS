# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from graphics_primitives_qualify import NAME, EXPECTED_DISKS, validate_layout, stress_result

ARTIFACTS = ROOT / 'bench/artifacts' / NAME
RESULTS = ROOT / 'bench/results' / NAME


def layout_inputs():
    return [(ARTIFACTS / 'build/8502' / name).read_text() for name in
            ('udeks-8502.map', 'udeks-8502-panic-probe.map')] + [
                (RESULTS / 'gateway-exports.txt').read_text()]


class GraphicsPrimitivesIntegrationTests(unittest.TestCase):
    def test_installed_layout_and_fixed_abis(self):
        layout = validate_layout(*layout_inputs())
        report = json.loads((RESULTS / 'qualification.json').read_text())
        for name, value in layout.items():
            self.assertEqual(report[name], value)
        self.assertEqual(layout['net_saved'], 173)
        self.assertEqual(layout['gateway_sizes'], [254, 46, 68, 358])
        self.assertEqual(layout['segments']['VICSHADOW']['start'], 0xA1E0)
        self.assertEqual(layout['segments']['VICSHADOW']['end'], 0xC11F)

    def test_layout_growth_and_zp_drift_fail(self):
        normal, panic, dump = layout_inputs()
        for broken in (normal.replace('00A1E0', '00A1E1'),
                       re.sub(r'(vic_pixel.o:\n[^\n]*Size=)0000BE', r'\g<1>0000BF', normal),
                       re.sub(r'(\bsp\s+)000006(\s+RLZ)', r'\g<1>000007\2', normal)):
            self.assertNotEqual(broken, normal)
            with self.assertRaises(ValueError):
                validate_layout(broken, broken, dump)
        with self.assertRaises(ValueError):
            validate_layout(normal, panic, '')

    def test_preserved_input_stress_and_honest_completion_metrics(self):
        report = json.loads((RESULTS / 'qualification.json').read_text())
        for label in ('baseline', 'd71', 'd64'):
            text = (RESULTS / f'build/raster-primitives-{label}.log').read_text()
            self.assertEqual(stress_result(text), report['native'][label])
        self.assertEqual(report['native']['d71'], report['native']['d64'])
        self.assertLess(report['native']['d71']['partial'], report['native']['baseline']['partial'])
        self.assertLess(report['native']['d71']['cached'], report['native']['baseline']['cached'])
        # The script resumes with a different amount of remaining paint work.
        # Do not erase the slower post-last-release metric or claim GUI acceptance.
        self.assertEqual(report['native']['d71']['remaining_replay'], 970)
        self.assertEqual(report['native']['baseline']['remaining_replay'], 674)
        self.assertIn('not installed', report['pixel_cache'])
        self.assertIn('pending', report['physical_hardware'])

    def test_incomplete_drag_evidence_is_rejected(self):
        text = (RESULTS / 'build/raster-primitives-d71.log').read_text()
        for broken in (text.replace('stress 3:', 'missing 3:'),
                       text.replace('leases=21', 'leases=20'),
                       text.replace('max partial=171', 'max partial=172'),
                       text.replace('PASS:', 'FAIL:')):
            with self.assertRaises(ValueError):
                stress_result(broken)

    def test_cache_budget_includes_only_owned_named_padding(self):
        report = json.loads((RESULTS / 'build/graphics-cache-placement/report.json').read_text())
        self.assertEqual(report['candidate']['qualified_reserve'], 222)
        self.assertEqual(report['candidate']['additional_bytes_before_bindings'], 801)
        self.assertEqual(report['post_shadow']['unowned_bytes'], 0)
        self.assertEqual(report['primitive_placement_padding'], 173)
        self.assertEqual(report['integrated_primitives'], {'pixel': {'CODE': 190}, 'span': {'CODE': 102}})
        self.assertTrue(all(not item['available_to_cache'] for item in report['other_regions']))

    def test_bitmap_equality_and_immutable_artifact_hashes(self):
        shadow_dir = RESULTS / 'build/vice/raster-primitives-shadow'
        shadow = (shadow_dir / 'shadow-drawn.bin').read_bytes()
        bitmap = (shadow_dir / 'vic-bitmap.bin').read_bytes()
        self.assertEqual(len(shadow), 8000)
        self.assertEqual(shadow, bitmap)
        for name, sha in EXPECTED_DISKS.items():
            self.assertEqual(hashlib.sha256((ARTIFACTS / 'build/boot' / name).read_bytes()).hexdigest(), sha)
        for directory in (ARTIFACTS, RESULTS):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), sha, name)

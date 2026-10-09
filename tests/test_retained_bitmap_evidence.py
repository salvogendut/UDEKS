# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep the completed target proof bound to its maps and emulator disks."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_window_cache import layout_maps
from placement_audit import parse_map

EVIDENCE=ROOT/'bench/results/2026-10-09-retained-bitmap'


class RetainedBitmapEvidence(unittest.TestCase):
    def setUp(self):
        self.report=json.loads((EVIDENCE/'report.json').read_text())

    def test_checksums_target_program_and_maps_are_bound(self):
        for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
            expected,name=line.split('  ',1)
            self.assertEqual(hashlib.sha256((EVIDENCE/name).read_bytes()).hexdigest(),expected,name)
        for original,saved in (
            ('build/bitmap-store/retained-check','sim6502/check'),
            ('build/bitmap-store/retained-check.map','sim6502/check.map'),
            ('build/8502/udeks-8502.map','maps/normal.map'),
            ('build/8502/udeks-8502-panic-probe.map','maps/panic.map')):
            self.assertEqual(hashlib.sha256((EVIDENCE/saved).read_bytes()).hexdigest(),
                self.report['source_and_build_sha256'][original])
        self.assertEqual((EVIDENCE/'sim6502/check.log').read_text(),
            f"PASS {self.report['target_checks']} retained bitmap checks: shared allocator, request parity and pixels\n")
        self.assertEqual(self.report['target_checks'],22462)

    def test_real_placement_keeps_pool_and_measures_unlinked_renderer(self):
        normal=(EVIDENCE/'maps/normal.map').read_text()
        segments=layout_maps(normal,(EVIDENCE/'maps/panic.map').read_text())
        modules,_=parse_map(normal)
        self.assertEqual(modules['retained_pool.o'],dict(BSS=5,GRAPHICSCODE=154))
        self.assertNotIn('retained_bitmap.o',modules)
        self.assertNotIn('bitmap_store.o',modules)
        self.assertEqual((self.report['pool_address'],self.report['pool_bytes']),(0x1300,2304))
        self.assertEqual(segments['BSS'][1],0x9080)
        self.assertEqual(self.report['resident_free_bytes'],0x93d0-0x9081)
        self.assertEqual(self.report['graphics_segment_free'],0x1300-segments['GRAPHICSCODE'][1]-1)
        self.assertEqual(self.report['path_segment_free'],0x9aa8-segments['GRAPHICSPATHS'][1]-1)
        candidate=self.report['prototype_request_and_renderer']
        self.assertEqual((candidate['CODE'],candidate['BSS']),(1386,29))
        self.assertEqual(self.report['minimum_resident_shortfall_before_adapter_and_extra_helpers'],568)

    def test_emulator_regressions_use_qualified_disks_and_match_canvases(self):
        vice=json.loads((EVIDENCE/'vice/d71.json').read_text())
        native=json.loads((EVIDENCE/'1986/d81.json').read_text())
        self.assertEqual(vice['disk_sha256'],self.report['disk_sha256']['d71'])
        self.assertEqual(native['disk_sha256'],self.report['disk_sha256']['d81'])
        self.assertEqual(native['exit_status'],0)
        self.assertTrue(native['four_native'])
        self.assertIn('PASS four native:',(EVIDENCE/'1986/d81.log').read_text())
        self.assertEqual(vice['checks'][-1]['command'],'echo four-slot cleanup passed')
        for tag in ('four-defaults','four-resized'):
            shadow=(EVIDENCE/f'vice/{tag}-shadow.bin').read_bytes()
            bitmap=(EVIDENCE/f'vice/{tag}-bitmap.bin').read_bytes()
            self.assertEqual((len(shadow),len(bitmap)),(8002,8002))
            self.assertEqual((shadow[:2],bitmap[:2]),(b'\xe0\xa1',b'\0\x60'))
            self.assertTrue(any(shadow[2:]))
            self.assertEqual(shadow[2:],bitmap[2:])  # VICE load-address headers differ


if __name__=='__main__':
    unittest.main()

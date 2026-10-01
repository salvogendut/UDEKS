# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from banked_loader_probe import fixture

A = ROOT/'bench/artifacts/2026-10-01-banked-loader'
R = ROOT/'bench/results/2026-10-01-banked-loader'


class BankedLoaderEvidence(unittest.TestCase):
    def test_checksums_and_exact_payloads(self):
        for directory in (A, R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(), expected)
        for suffix, drive in (('d64', '1541'), ('d71', '1571')):
            folder = R/('vice-'+suffix)
            report = json.loads((folder/'result.json').read_text())
            self.assertEqual(report['disk_sha256'], hashlib.sha256((A/('loader-test.'+suffix)).read_bytes()).hexdigest())
            self.assertEqual(report['loader_sha256'], hashlib.sha256((A/'banked-loader.bin').read_bytes()).hexdigest())
            self.assertEqual(report['drive'], drive)
            self.assertTrue(report['load_only'])
            self.assertTrue(report['legacy_code_preserved'])
            self.assertTrue(report['console_alive'])
            for slot, base, capacity in ((3, 0x2300, 0x1200), (4, 0x3500, 0xB00)):
                actual = (folder/('app'+str(slot)+'.bin')).read_bytes()
                self.assertEqual(actual[:2], base.to_bytes(2, 'little'))
                self.assertEqual(actual[2:], fixture(base, capacity-16, 16)[16:]+bytes(16))
            records = report['records']
            for item in records:
                self.assertTrue(item['request_preserved'])
                self.assertTrue(item['kernel_map_restored'])
            pairs = {(r['name'], r['errno']) for r in records}
            for name, error in (('full3',0), ('full4',0), ('magic',8), ('short',8),
                                ('trail',8), ('bss',12), ('over',12), ('absent',2),
                                ('padding',22), ('../bad',22)):
                self.assertIn((name,error), pairs)
            self.assertEqual(sum(r['errno']==16 for r in records), 13)

    def test_legacy_calculator_and_canvas_regression(self):
        report = json.loads((R/'legacy/result.json').read_text())
        self.assertEqual(report['disk_sha256'], hashlib.sha256((A/'udeks.d64').read_bytes()).hexdigest())
        self.assertTrue(report['image_matches_disk'])
        self.assertTrue(report['shadow_matches_bitmap'])
        self.assertEqual([r['hundredths'] for r in report['records'] if 'expression' in r], [400,300,475])
        bitmap = (R/'legacy/bitmap.bin').read_bytes()
        shadow = (R/'legacy/shadow.bin').read_bytes()
        self.assertEqual(len(bitmap), 8002)
        self.assertEqual(bitmap[2:], shadow[2:])

# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / 'bench/artifacts/2026-09-30-xcalc'
R = ROOT / 'bench/results/2026-09-30-xcalc'


class XcalcEvidenceTests(unittest.TestCase):
    def test_preserved_images_and_results(self):
        for directory in (A, R):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), expected)
        app = (A / 'xcalc.udx').read_bytes()
        self.assertEqual(app[:4], b'UDEX')
        size, bss = (int.from_bytes(app[i:i+2], 'little') for i in (10, 12))
        self.assertEqual((size, bss), (3993, 34))
        self.assertEqual(len(app), size + 16)
        self.assertLessEqual(size + bss, 4096)

    def test_vice_payloads_and_native_input(self):
        for suffix in ('d64', 'd71'):
            folder = R / ('vice-' + suffix)
            result = json.loads((folder / 'result.json').read_text())
            self.assertEqual(result['disk_sha256'], hashlib.sha256((A / ('udeks.' + suffix)).read_bytes()).hexdigest())
            self.assertTrue(result['image_matches_disk'])
            self.assertTrue(result['shadow_matches_bitmap'])
            self.assertEqual([r['hundredths'] for r in result['records'] if 'expression' in r], [400, 300, 475])
            shadow = (folder / 'shadow.bin').read_bytes()
            bitmap = (folder / 'bitmap.bin').read_bytes()
            self.assertEqual(shadow[:2], b'\xe0\xa1')
            self.assertEqual(bitmap[:2], b'\x00\x60')
            self.assertEqual(len(shadow), 8002)
            self.assertEqual(shadow[2:], bitmap[2:])
        native = json.loads((R / '1986/result.json').read_text())
        self.assertEqual(native['exit_status'], 0)
        self.assertTrue(native['xcalc'])
        for key, name in (('disk_sha256', 'udeks.d64'), ('test_disk_sha256', '1986-test.d64')):
            self.assertEqual(native[key], hashlib.sha256((A / name).read_bytes()).hexdigest())
        self.assertIn('PASS xcalc: native mouse arithmetic, drag, console, slot conflicts, wave coexistence, restart, Ctrl+C', (R / '1986/run.log').read_text())

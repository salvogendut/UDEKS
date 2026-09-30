# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT/'bench/artifacts/2026-09-30-bank-probe-fix'
RESULTS = ROOT/'bench/results/2026-09-30-bank-probe-fix'


def missing_border(bitmap, x, y, width, height):
    assert len(bitmap) == 8000
    assert 0 <= x < x+width <= 320 and 0 <= y < y+height <= 200
    return sum(not (bitmap[(yy//8)*320+(xx//8)*8+yy%8] & (128 >> (xx%8)))
               for yy in range(y, y+height) for xx in range(x, x+width)
               if xx in (x, x+width-1) or yy in (y, y+height-1))


class BankProbeRegressionTests(unittest.TestCase):
    def test_exact_runtime_corruption_and_repair(self):
        linked = (ARTIFACTS/'udeks-8502.bin').read_bytes()[0x6000:0x6008]
        before = (RESULTS/'before-site.bin').read_bytes()
        after = (RESULTS/'after-site.bin').read_bytes()
        self.assertEqual(linked[0], 0x06)
        self.assertEqual(before, b'\xa0'+linked[1:])
        self.assertEqual(after, linked)

    def test_native_visual_failure_then_repeated_drag_success(self):
        before = json.loads((RESULTS/'before-1986.json').read_text())
        after = json.loads((RESULTS/'after-1986.json').read_text())
        self.assertEqual(before['exit_status'], 1)
        self.assertEqual(after['exit_status'], 0)
        for phase, record, base in [('before', before, 0xf228), ('after', after, 0xf274)]:
            self.assertTrue(record['raw_iec'] and record['drag_regression'])
            status = (RESULTS/(phase+'-status.bin')).read_bytes()
            geometry = status[base-0xf040:base-0xf040+4]
            missing = missing_border((RESULTS/(phase+'-bitmap.bin')).read_bytes(), *geometry)
            self.assertEqual(missing, 294 if phase == 'before' else 0)
        self.assertEqual((RESULTS/'after-1986.log').read_text().count('missing pixels'), 14)
        self.assertEqual(hashlib.sha256((ARTIFACTS/'udeks.d64').read_bytes()).hexdigest(),
                         after['disk_sha256'])

    def test_preserved_evidence_hashes(self):
        for directory in (ARTIFACTS, RESULTS):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                digest, name = line.split(maxsplit=1)
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(), digest)


if __name__ == '__main__': unittest.main()

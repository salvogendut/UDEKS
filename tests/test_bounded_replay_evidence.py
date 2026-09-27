# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = '2026-09-28-bounded-replay'

class BoundedReplayEvidenceTests(unittest.TestCase):
    def test_saved_hashes_and_source(self):
        for kind in ('artifacts', 'results'):
            directory = ROOT / 'bench' / kind / NAME
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                digest, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest, name)
        artifact = ROOT / 'bench/artifacts' / NAME
        self.assertIn('if (udeks_window_is_focused(handle) != 0)',
                      (artifact / 'xwave.c').read_text())

    def test_native_final_replay_and_transport(self):
        results = ROOT / 'bench/results' / NAME
        for name in ('d71', 'd64'):
            log = (results / f'{name}.log').read_text()
            self.assertEqual(len(re.findall(r'^stress \d+:', log, re.M)), 32)
            self.assertIn('replay: completed in 674 PAL frames after last release; leases=21', log)
            self.assertIn('drag release max partial=279 cached=266', log)
            self.assertIn('PASS: repeated native wave drags and console cancellation', log)
            self.assertIn('xwave complete, 21 cached rows',
                          (results / f'vice-{name}.log').read_text())
        shadow = (results / 'raw/shadow-drawn.bin').read_bytes()
        bitmap = (results / 'raw/vic-bitmap.bin').read_bytes()
        self.assertEqual(shadow[:2], b'\xe0\xa1')
        self.assertEqual(bitmap[:2], b'\x00\x60')
        self.assertEqual(len(shadow), 8002)
        self.assertEqual(shadow[2:], bitmap[2:])

if __name__ == '__main__':
    unittest.main()

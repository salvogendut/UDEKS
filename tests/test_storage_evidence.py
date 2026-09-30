# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT/'bench/results/2026-09-30-storage-0.1'


class StorageEvidence(unittest.TestCase):
    def test_preserved_files_match_checksums(self):
        for directory in (RESULTS, ROOT/'bench/artifacts/2026-09-30-storage-0.1'):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                digest, name = line.split()
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(), digest)

    def test_native_results_include_tiny_files_and_media_recovery(self):
        for drive in ('1541', '1571'):
            result = json.loads((RESULTS/f'vice-{drive}-stream.json').read_text())
            self.assertEqual(result['exact_file_sizes'],
                {'TWO': 2, 'EDGE': 24, 'BIN': 515, 'ONE': 1, 'EMPTY': 0, 'BOUND': 255})
            self.assertTrue(result['bitmap_unchanged'])
            self.assertTrue(result['media_recovery'])
            self.assertEqual(result['remount_retry_errors'], [5])
        result = json.loads((RESULTS/'1986.json').read_text())
        self.assertEqual(result['exit_status'], 0)
        self.assertTrue(result['raw_iec'])

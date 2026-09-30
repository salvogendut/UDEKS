# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from disk_shell_fixture import build_fixture, shell_file


class DiskShellEvidence(unittest.TestCase):
    def test_exact_images_source_changes_and_recovery(self):
        artifacts = ROOT/'bench/artifacts/2026-09-30-disk-shell'
        results = ROOT/'bench/results/2026-09-30-disk-shell'
        digest = lambda data: hashlib.sha256(data).hexdigest()
        for directory in (artifacts, results):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertEqual(digest((directory/name).read_bytes()), expected)
        cases = {'diskA': (1, 0, 'diskA'), 'diskB': (1, 0, 'diskB'),
                 'missing': (2, 11, '0.1.0'), 'bad': (2, 4, '0.1.0'),
                 'entry': (2, 10, '0.1.0'), 'flags': (2, 7, '0.1.0')}
        for drive, suffix in (('1541', 'd64'), ('1571', 'd71')):
            base = (artifacts/f'udeks.{suffix}').read_bytes()
            test = (artifacts/f'udeks-disk-shell.{suffix}').read_bytes()
            _, base_offsets = shell_file(base)
            _, test_offsets = shell_file(test)
            self.assertEqual(bytes(base[p] for p in base_offsets), bytes(test[p] for p in test_offsets))
            record = json.loads((results/f'vice-{drive}.json').read_text())
            self.assertEqual(record['disk_sha256'], digest(base))
            self.assertEqual([run['variant'] for run in record['runs']], list(cases))
            for run in record['runs']:
                source, error, version = cases[run['variant']]
                self.assertEqual((run['source'], run['error']), (source, error))
                self.assertEqual(run['disk_sha256'], digest(build_fixture(base, run['variant'])))
                self.assertIn('UDEKS '+version+' c128 8502', run['commands'][0]['console'])
                self.assertEqual([command['command'] for command in run['commands']],
                    ['uname -a', 'mount 8 /mnt', 'cat /mnt/HELLO', 'umount /mnt', 'cowsay recovered'])
        test_hash = digest((artifacts/'udeks-disk-shell.d64').read_bytes())
        native = json.loads((results/'1986.json').read_text())
        self.assertEqual(native['disk_sha256'], test_hash)
        self.assertEqual(native['exit_status'], 0)
        self.assertTrue(native['raw_iec'] and native['disk_shell'] and native['disk_exec'])
        regression = json.loads((results/'disk-exec-1541.json').read_text())
        self.assertEqual(regression['disk_sha256'], test_hash)
        self.assertEqual(len(regression['commands']), 43)

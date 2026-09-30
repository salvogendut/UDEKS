# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DiskExecEvidence(unittest.TestCase):
    def test_preserved_hashes_and_runtime_image_binding(self):
        artifacts = ROOT/'bench/artifacts/2026-09-30-storage-0.2'
        results = ROOT/'bench/results/2026-09-30-storage-0.2'
        for directory in (artifacts, results):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                digest, name = line.split()
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(), digest)
        for drive, suffix in (('1541', 'd64'), ('1571', 'd71')):
            record = json.loads((results/f'vice-{drive}.json').read_text())
            self.assertEqual(record['disk_sha256'], hashlib.sha256(
                (artifacts/f'udeks-disk-exec.{suffix}').read_bytes()).hexdigest())
            commands = [item['command'] for item in record['commands']]
            self.assertEqual(commands.count('/mnt/DISKCOW busy'), 2)
            for command in ('/mnt/DISKCOW hello', '/mnt/ENTRY', '/mnt/LIMIT',
                            '/mnt/CPU', '/mnt/FLAGS', '/mnt/TRAIL', '/mnt/SIZE',
                            '/mnt/DISKCOW removed', '/mnt/DISKCOW restored', 'xclock &', 'xwave &'):
                self.assertIn(command, commands)
        native = json.loads((results/'1986.json').read_text())
        self.assertEqual(native['exit_status'], 0)
        self.assertTrue(native['raw_iec'] and native['disk_exec'])
        self.assertEqual(native['disk_sha256'], hashlib.sha256(
            (artifacts/'udeks-disk-exec.d64').read_bytes()).hexdigest())

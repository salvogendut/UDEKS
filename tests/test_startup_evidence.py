# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from startup_probe import fixture
from disk_shell_fixture import build_fixture


class StartupEvidence(unittest.TestCase):
    def test_exact_images_and_live_feature_results(self):
        artifacts = ROOT/'bench/artifacts/2026-09-30-startup-sysinfo'
        results = ROOT/'bench/results/2026-09-30-startup-sysinfo'
        digest = lambda data: hashlib.sha256(data).hexdigest()
        for directory in (artifacts, results):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertEqual(digest((directory/name).read_bytes()), expected)
        script = b'# boot policy\r\n\necho RC-START\nmount 8 /mnt\nxinit\nxclock &\necho RC-END'
        for drive, suffix, total, free in (('1541', 'd64', 664, 206), ('1571', 'd71', 1328, 870)):
            base = (artifacts/f'udeks.{suffix}').read_bytes()
            record = json.loads((results/f'vice-{drive}.json').read_text())
            self.assertEqual(record['disk_sha256'], digest(fixture(base, script)))
            self.assertEqual((record['total'], record['free']), (total, free))
            self.assertTrue(record['driver_intact'])
            self.assertIn('RC-END', record['boot_console'])
            self.assertEqual([r['command'] for r in record['commands']], [
                'free', 'df', '/mnt/DF /mnt', 'df /bad', 'cat /mnt/HELLO',
                'ls /mnt', 'umount /mnt', 'cowsay OK', 'uname -a'])
            self.assertIn('total 2560  used 0  free 2560', record['commands'][0]['console'])
        base = (artifacts/'udeks.d64').read_bytes()
        self.assertEqual((artifacts/'udeks-rc-demo.d64').read_bytes(), fixture(base, script))
        for variant, script in (('invalid', b'echo MUST-NOT-RUN\n\x01'), ('missing', None)):
            record = json.loads((results/f'{variant}.json').read_text())
            self.assertEqual(record['disk_sha256'], digest(fixture(base, script)))
            self.assertNotIn('MUST-NOT-RUN', record['boot_console'])
            self.assertEqual('RC failed' in record['boot_console'], variant == 'invalid')
            self.assertTrue(record['driver_intact'])
        native = json.loads((results/'1986.json').read_text())
        self.assertEqual(native['disk_sha256'], digest((artifacts/'udeks-test.d64').read_bytes()))
        self.assertEqual(native['exit_status'], 0)
        self.assertTrue(native['sysinfo'] and native['disk_shell'] and native['disk_exec'] and native['raw_iec'])
        self.assertEqual((results/'drawn.bin').read_bytes(), (results/'vic.bin').read_bytes())
        recovery = json.loads((results/'recovery.json').read_text())
        self.assertEqual(recovery['disk_sha256'], digest(base))
        self.assertEqual(len(recovery['runs']), 6)
        for run in recovery['runs']:
            self.assertEqual(run['disk_sha256'], digest(build_fixture(base, run['variant'])))

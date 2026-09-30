# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from managed_app_fixture import dos_file

ARTIFACTS = ROOT/'bench/artifacts/2026-09-30-default-mount'
RESULTS = ROOT/'bench/results/2026-09-30-default-mount'
PREVIOUS = ROOT/'bench/artifacts/2026-09-30-bank-probe-fix'


class DefaultMountEvidence(unittest.TestCase):
    def test_only_rc_sector_changes_in_each_disk(self):
        for name in ('udeks.d64', 'udeks.d71', 'udeks-boot-debug.d64'):
            old = (PREVIOUS/name).read_bytes()
            new = (ARTIFACTS/name).read_bytes()
            _, offsets = dos_file(new, 'RC')
            script = bytes(new[p] for p in offsets)
            self.assertEqual(script, (ARTIFACTS/'rc').read_bytes())
            self.assertEqual([line for line in script.splitlines() if line and not line.startswith(b'#')],
                             [b'mount 8 /mnt'])
            self.assertEqual(len(old), len(new))
            self.assertEqual({i//256 for i, (a, b) in enumerate(zip(old, new)) if a != b},
                             {offsets[0]//256})

    def test_both_vice_drives_launch_apps_without_manual_mount(self):
        for drive, suffix in (('1541', 'd64'), ('1571', 'd71')):
            record = json.loads((RESULTS/('vice-'+drive+'.json')).read_text())
            self.assertEqual(record['variant'], 'default')
            commands = [command['command'] for command in record['commands']]
            self.assertEqual(commands[:2], ['xclock &', 'xwave &'])
            self.assertNotIn('mount 8 /mnt', commands)
            self.assertTrue(record['driver_intact'])
            self.assertEqual(record['disk_sha256'], hashlib.sha256((ARTIFACTS/('udeks.'+suffix)).read_bytes()).hexdigest())
        native = json.loads((RESULTS/'1986.json').read_text())
        self.assertTrue(native['raw_iec'] and native['boot_mounted'] and native['drag_regression'])
        self.assertEqual(native['exit_status'], 0)
        log = (RESULTS/'1986.log').read_text()
        self.assertNotIn('command mount', log)
        self.assertEqual(log.count('0 missing pixels'), 14)

    def test_preserved_hashes(self):
        for directory in (ARTIFACTS, RESULTS):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                digest, name = line.split(maxsplit=1)
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(), digest)


if __name__ == '__main__': unittest.main()

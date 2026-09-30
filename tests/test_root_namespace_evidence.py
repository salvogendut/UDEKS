# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from disk_shell_fixture import build_fixture
from managed_app_fixture import dos_file
from startup_probe import fixture

A = ROOT/'bench/artifacts/2026-09-30-root-namespace'
R = ROOT/'bench/results/2026-09-30-root-namespace'
digest = lambda data: hashlib.sha256(data).hexdigest()
record = lambda name: json.loads((R/(name+'.json')).read_text())


class RootNamespaceEvidence(unittest.TestCase):
    def test_preserved_bytes_build_bounds_and_clean_reproduction(self):
        for directory in (A, R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split(maxsplit=1)
                self.assertEqual(digest((directory/name).read_bytes()), expected)
        shell = (A/'ush.udx').read_bytes()
        size, bss = (int.from_bytes(shell[i:i+2], 'little') for i in (10, 12))
        self.assertEqual((size, bss), (3588, 368))
        self.assertLessEqual(size+bss, 4096)
        self.assertEqual(len(shell), size+16)
        self.assertLessEqual(len((A/'bootfs.img').read_bytes()), 4096)
        self.assertLessEqual(len((A/'policy.bin').read_bytes()), 8192)
        for line in (R/'clean-disks.sha256').read_text().splitlines():
            expected, name = line.split()
            self.assertEqual(digest((A/name).read_bytes()), expected)
        self.assertEqual((R/'shadow.bin').read_bytes(), (R/'vic.bin').read_bytes())
        self.assertEqual(len((R/'shadow.bin').read_bytes()), 8000)
        self.assertIn('task-SPAWN probe OK', (R/'spawn.log').read_text())

    def test_system_commands_survive_independent_device_nine(self):
        for drive, suffix in (('1541', 'd64'), ('1571', 'd71')):
            disk = (A/('udeks.'+suffix)).read_bytes()
            result = record('vice-'+drive)
            self.assertEqual(result['disk_sha256'], digest(disk))
            self.assertEqual(result['data_sha256'], digest((A/'data.d64').read_bytes()))
            self.assertTrue(result['driver_intact'])
            self.assertFalse(result['recovery'])
            commands = {r['command']: r['console'] for r in result['commands']}
            # df /mnt is run both before and after mounting; check both records.
            reports = [r['console'] for r in result['commands'] if r['command'] == 'df /mnt']
            self.assertIn('not mounted', reports[0])
            self.assertIn('iec9', reports[1])
            self.assertIn('DEVICE NINE DATA', commands['cat HELLO'])
            self.assertIn('system-still-here', commands['cowsay system-still-here'])
            self.assertIn('xwave started &', commands['xwave &'])
            self.assertIn('Device 8 is already', commands['cat /etc/rc'])
            for name in ('USH.BIN', 'RC.ETC', 'CAT.BIN', 'MOUNT.BIN', 'XCLOCK.BIN', 'XWAVE.BIN'):
                dos_file(disk, name)
            _, offsets = dos_file(disk, 'USH.BIN')
            self.assertEqual(bytes(disk[p] for p in offsets), (A/'ush.udx').read_bytes())

    def test_startup_variants_and_explicit_recovery(self):
        image = (A/'udeks.d64').read_bytes()
        scripts = {
            'valid': b'# boot policy\r\n\necho RC-START\nmount 8 /mnt\nxinit\nxclock &\necho RC-END',
            'invalid': b'echo MUST-NOT-RUN\n\x01', 'missing': None,
        }
        for name, script in scripts.items():
            result = record('startup-'+name)
            self.assertEqual(result['disk_sha256'], digest(fixture(image, script)))
            self.assertTrue(result['driver_intact'])
            self.assertEqual('RC failed' in result['boot_console'], name == 'invalid')
            self.assertNotIn('MUST-NOT-RUN', result['boot_console'])
            if name == 'valid': self.assertIn('RC-END', result['boot_console'])
        recovery = record('recovery')
        self.assertTrue(recovery['recovery'] and recovery['driver_intact'])
        self.assertEqual(recovery['disk_sha256'], digest(build_fixture(image, 'missing')))
        self.assertIn('/mnt/RECOVER recovery', [r['command'] for r in recovery['commands']])

    def test_native_input_dragging_and_typed_boot(self):
        expected = digest((A/'udeks.d64').read_bytes())
        native = record('1986')
        self.assertEqual(native['disk_sha256'], expected)
        self.assertEqual(native['test_disk_sha256'], digest((A/'1986-test.d64').read_bytes()))
        self.assertEqual(native['exit_status'], 0)
        self.assertTrue(native['raw_iec'] and native['root_namespace'])
        log = (R/'1986.log').read_text()
        self.assertEqual(log.count('0 missing pixels'), 14)
        self.assertIn('PASS root namespace/cwd/data-alias/unmount', log)
        self.assertEqual(record('typed-boot')['disk_sha256'], expected)
        self.assertEqual(record('typed-boot')['entry'], 'BASIC BOOT')

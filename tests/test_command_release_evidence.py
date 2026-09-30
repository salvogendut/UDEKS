# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from boot_banner_probe import fixture

A = ROOT/'bench/artifacts/2026-09-30-command-release'
R = ROOT/'bench/results/2026-09-30-command-release'
digest = lambda b: hashlib.sha256(b).hexdigest()
record = lambda name: json.loads((R/(name+'.json')).read_text())


class CommandRelease(unittest.TestCase):
    def test_preserved_bytes_and_shell_bounds(self):
        for directory in (A, R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split(maxsplit=1)
                self.assertEqual(digest((directory/name).read_bytes()), expected)
        shell = (A/'ush.udx').read_bytes()
        image = int.from_bytes(shell[10:12], 'little')
        bss = int.from_bytes(shell[12:14], 'little')
        self.assertEqual((image, bss), (3723, 368))
        self.assertLessEqual(image+bss, 4096)
        self.assertEqual(len(shell), image+16)
        self.assertEqual((A/'stage1.bin').read_bytes()[0x3bb:0x3c0], b'\xa9\xff\x20\x90\xff')
        self.assertEqual((R/'shadow.bin').read_bytes(), (R/'vic.bin').read_bytes())
        for line in (R/'clean-disks.sha256').read_text().splitlines():
            expected, name = line.split()
            self.assertEqual(digest((A/name).read_bytes()), expected)
        self.assertEqual((R/'spawn.log').read_text().count('task-SPAWN probe OK'), 2)

    def test_actual_boot_header_detection_and_mount_success(self):
        image = (A/'udeks.d64').read_bytes()
        banner = record('banner')
        self.assertEqual(banner['source_sha256'], digest(image))
        self.assertEqual([r['flags'] for r in banner['runs']], ['0101','0001','0100','0000'])
        for r in banner['runs']:
            self.assertEqual(r['disk_sha256'], digest(fixture(image, r['variant'])))
            rows = [s for s in r['console'].splitlines() if 'HEADER ...' in s]
            self.assertEqual(len(rows), 2)
            self.assertEqual([s.endswith('[ OK ]') for s in rows], [bool(v) for v in bytes.fromhex(r['flags'])])
        for drive, suffix in (('1541','d64'), ('1571','d71')):
            r = record('vice-'+drive)
            self.assertEqual(r['disk_sha256'], digest((A/('udeks.'+suffix)).read_bytes()))
            self.assertIn('mount: /mnt ready (read-only)', r['boot_console'])
            self.assertTrue(r['driver_intact'])
            self.assertEqual([c['command'] for c in r['commands'][:2]], ['xclock &', 'xwave &'])

    def test_errors_dragging_recovery_and_typed_boot(self):
        image_hash = digest((A/'udeks.d64').read_bytes())
        managed = record('managed')
        self.assertEqual(managed['disk_sha256'], image_hash)
        self.assertTrue(managed['code_matches_disk'] and managed['retained_restart_without_media'])
        console = '\n'.join(c['console'] for c in managed['commands'])
        for error in ('not ready', 'already running', 'not found; check /mnt', 'slot busy', 'bad program', 'I/O error'):
            self.assertIn(': '+error, console)
        self.assertNotIn('request failed', console)
        native = record('1986')
        self.assertEqual(native['disk_sha256'], image_hash)
        self.assertEqual(native['exit_status'], 0)
        self.assertTrue(native['raw_iec'] and native['drag_regression'] and native['boot_mounted'])
        self.assertEqual((R/'1986.log').read_text().count('0 missing pixels'), 14)
        self.assertTrue(record('recovery')['recovery'])
        self.assertEqual(record('typed-boot')['disk_sha256'], image_hash)
        self.assertEqual(record('typed-boot')['entry'], 'BASIC BOOT')


if __name__ == '__main__': unittest.main()

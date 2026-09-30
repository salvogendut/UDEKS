# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from managed_app_fixture import dos_file, ERRORS
from build_d71 import install_prg_file
from startup_probe import fixture as startup_fixture

A = ROOT/'bench/artifacts/2026-09-30-disk-graphics'
R = ROOT/'bench/results/2026-09-30-disk-graphics'
digest = lambda data: hashlib.sha256(data).hexdigest()


class ManagedDiskEvidence(unittest.TestCase):
    def test_exact_candidate_and_emulator_results(self):
        for directory in (A, R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertEqual(digest((directory/name).read_bytes()), expected)
        bootfs = (A/'bootfs.img').read_bytes()
        names = [bootfs[24+24*n:40+24*n].split(b'\0')[0].decode() for n in range(bootfs[6])]
        self.assertNotIn('xclock', names); self.assertNotIn('xwave', names)
        for drive, suffix, first in (('1541', 'd64', 'xclock'), ('1571', 'd71', 'xwave')):
            image = (A/f'udeks.{suffix}').read_bytes()
            record = json.loads((R/f'vice-{drive}.json').read_text())
            self.assertEqual(record['disk_sha256'], digest(image))
            self.assertEqual(record['first'], first)
            self.assertEqual(record['bootfs_names'], names)
            self.assertTrue(record['code_matches_disk'] and record['retained_restart_without_media'])
            for name in ('xclock', 'xwave'):
                _, offsets = dos_file(image, name.upper())
                self.assertEqual(bytes(image[p] for p in offsets), (A/(name+'.udx')).read_bytes())
        faults = json.loads((R/'vice-1541.json').read_text())
        rejects = [bytes.fromhex(c['loader'])[6] for c in faults['commands'] if c['command'] == 'xwave &']
        self.assertEqual(rejects[:len(ERRORS)], list(ERRORS.values()))

    def test_native_input_and_regressions(self):
        native = json.loads((R/'1986.json').read_text())
        image = (A/'udeks.d64').read_bytes()
        self.assertEqual(native['disk_sha256'], digest(image))
        self.assertEqual(native['exit_status'], 0)
        self.assertTrue(native['disk_graphics'] and native['raw_iec'] and native['disk_shell'])
        test = bytearray(image)
        install_prg_file(test, 'EMPTY', b'', file_type=0x81)
        install_prg_file(test, 'ONE', b'X', file_type=0x81)
        self.assertEqual(native['test_disk_sha256'], digest(test))
        self.assertIn('PASS disk graphics:', (R/'1986.log').read_text())
        self.assertNotIn('FAIL:', (R/'1986.log').read_text())
        self.assertIn('task-SPAWN probe OK', (R/'spawn.log').read_text())
        self.assertIn('shadow probe OK', (R/'shadow.log').read_text())
        self.assertEqual((R/'drawn.bin').read_bytes(), (R/'vic.bin').read_bytes())
        disk = json.loads((R/'disk-exec.json').read_text())
        self.assertEqual(disk['disk_sha256'], digest((A/'udeks-test.d64').read_bytes()))
        startup = json.loads((R/'startup.json').read_text())
        script = b'# boot policy\r\n\necho RC-START\nmount 8 /mnt\nxinit\nxclock &\necho RC-END'
        self.assertEqual(startup['disk_sha256'], digest(startup_fixture(image, script)))
        self.assertIn('RC-END', startup['boot_console'])
        self.assertTrue(startup['driver_intact'])

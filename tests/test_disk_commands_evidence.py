# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from managed_app_fixture import dos_file
from disk_shell_fixture import build_fixture
from build_d71 import install_prg_file
from startup_probe import fixture as startup_fixture

A = ROOT/'bench/artifacts/2026-09-30-disk-commands'
R = ROOT/'bench/results/2026-09-30-disk-commands'
digest = lambda b: hashlib.sha256(b).hexdigest()


class DiskCommandEvidence(unittest.TestCase):
    def test_hashes_inventory_and_exact_program_bytes(self):
        for directory in (A, R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertEqual(digest((directory/name).read_bytes()), expected, name)
        bootfs = (A/'bootfs.img').read_bytes()
        names = [bootfs[24+24*n:40+24*n].split(b'\0')[0] for n in range(bootfs[6])]
        self.assertEqual(names, [b'mount', b'umount', b'ush'])
        for suffix in ('d64', 'd71'):
            image = (A/('udeks.'+suffix)).read_bytes()
            for file, program in {'USH':'ush', 'COWSAY':'cowsay', 'DATE':'date',
                'LS':'filetools', 'CAT':'filetools', 'FREE':'sysinfo', 'DF':'sysinfo',
                'UNAME':'diagnostics', 'LSHW':'diagnostics', 'LSMOD':'diagnostics',
                'LSCPU':'diagnostics', 'Z80CTL':'diagnostics', 'XCLOCK':'xclock', 'XWAVE':'xwave'}.items():
                _, offsets = dos_file(image, file)
                self.assertEqual(bytes(image[p] for p in offsets), (A/(program+'.udx')).read_bytes())

    def test_live_command_results_are_bound_to_candidate(self):
        for record, suffix, recovery in (('vice-1541', 'd64', False),
                ('vice-1571', 'd71', False), ('recovery', 'd71', True)):
            result = json.loads((R/(record+'.json')).read_text())
            image = (A/('udeks.'+suffix)).read_bytes()
            if recovery: image = build_fixture(image, 'missing')
            self.assertEqual(result['disk_sha256'], digest(image))
            commands = {c['command']:c['console'] for c in result['commands']}
            for command, text in (('uname -a', 'UDEKS 0.1.0'), ('/mnt/LSHW', 'Expansion:'),
                ('z80ctl test', 'Z80 self-test: OK'), ('xwave &', 'started in background'),
                ('xinit -q', 'VIC-II graphics stopped'), ('cowsay recovered', '^__^')):
                self.assertIn(text, commands[command])
        for record, suffix in (('managed', 'd64'), ('disk-exec', 'test.d64')):
            image = A/('udeks.d64' if suffix == 'd64' else 'udeks-test.d64')
            result = json.loads((R/(record+'.json')).read_text())
            self.assertEqual(result['disk_sha256'], digest(image.read_bytes()))

    def test_native_input_startup_stack_and_bitmap_regressions(self):
        image = (A/'udeks.d64').read_bytes()
        native = json.loads((R/'1986.json').read_text())
        self.assertEqual(native['disk_sha256'], digest(image))
        self.assertEqual(native['exit_status'], 0)
        self.assertTrue(native['disk_graphics'] and native['raw_iec'])
        fixture = bytearray(image)
        install_prg_file(fixture, 'EMPTY', b'', file_type=0x81)
        install_prg_file(fixture, 'ONE', b'X', file_type=0x81)
        self.assertEqual(native['test_disk_sha256'], digest(fixture))
        self.assertIn('PASS disk graphics:', (R/'1986.log').read_text())
        self.assertIn('task-SPAWN probe OK', (R/'spawn.log').read_text())
        self.assertIn('shadow probe OK', (R/'shadow.log').read_text())
        self.assertEqual((R/'drawn.bin').read_bytes(), (R/'vic.bin').read_bytes())
        startup = json.loads((R/'startup.json').read_text())
        script = b'# boot policy\r\n\necho RC-START\nmount 8 /mnt\nxinit\nxclock &\necho RC-END'
        self.assertEqual(startup['disk_sha256'], digest(startup_fixture(image, script)))
        self.assertTrue(startup['driver_intact'])
        self.assertIn('RC-END', startup['boot_console'])


if __name__ == '__main__': unittest.main()

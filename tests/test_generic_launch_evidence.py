# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from gen_capability_imports import map_exports
from o65_to_udex import pack_o65
from managed_app_fixture import dos_file
from add_disk_apps import add_apps
from generic_launch_probe import fixtures

A = ROOT/'bench/artifacts/2026-10-04-generic-launch'
R = ROOT/'bench/results/2026-10-04-generic-launch'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class GenericLaunchEvidence(unittest.TestCase):
    def test_hashes_and_independently_packaged_same_binary(self):
        for folder in (A, R):
            for line in (folder/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertEqual(digest(folder/name), expected, name)
        program = (A/'HELLO.BIN').read_bytes()
        entry = map_exports((A/'xhello.map').read_text())['_udeks_program_entry'][0]
        self.assertEqual(pack_o65((A/'xhello.o65').read_bytes(), entry), program)
        self.assertEqual(len(program), 597)
        for suffix in ('d64', 'd71'):
            normal = (A/('udeks.'+suffix)).read_bytes()
            demo = (A/('generic-demo.'+suffix)).read_bytes()
            self.assertEqual(demo, add_apps(normal, [('HELLO.BIN', program), ('SECOND.BIN', program)]))
            for name in ('HELLO', 'SECOND'):
                # Normal disks also contain an unrelated plain HELLO text file.
                _, offsets = dos_file(demo, name+'.BIN')
                self.assertEqual(bytes(demo[i] for i in offsets), program)
            qualified = (A/('qualification.'+suffix)).read_bytes()
            # Fault fixtures deliberately fail complete runtime validation;
            # recreate through the raw DOS writer, not the user installer.
            from build_d71 import install_prg_file
            expected = bytearray(normal)
            for name, data in fixtures(program).items():
                install_prg_file(expected, name.upper()+'.BIN', data, file_type=0x81)
            self.assertEqual(qualified, expected)

    def test_ordinary_shell_allocation_rejections_and_instance_reuse(self):
        for suffix, drive in (('d64', '1541'), ('d71', '1571')):
            folder = R/('vice-'+suffix)
            report = json.loads((folder/'result.json').read_text())
            self.assertEqual(report['drive'], drive)
            self.assertEqual(report['disk_sha256'], digest(A/('udeks.'+suffix)))
            self.assertEqual(report['fixture_sha256'], digest(A/('qualification.'+suffix)))
            self.assertEqual(report['program_sha256'], digest(A/'HELLO.BIN'))
            for flag in ('unknown_names','automatic_slots','legacy_stop_safe',
                         'independent_input','drag_close_reuse'):
                self.assertTrue(report[flag], flag)
            commands = [(r['command'], r['console']) for r in report['records']]
            for line, response in (('badmagic &','loader error'),('badpatch &','loader error'),
                ('absent &','Unknown command: absent'),('large &','task slot busy'),
                ('extra &','task slot busy'),('xcalc -q','xcalc: not ready'),
                ('xdraw -q','xdraw: not ready'),('echo slots reusable','slots reusable')):
                self.assertTrue(any(c==line and response in output for c, output in commands), line)
            self.assertEqual([c for c, _ in commands].count('xinit -q'), 2)
            self.assertEqual([c for c, _ in commands].count('large &'), 2)
            def raw(name): return (folder/(name+'.bin')).read_bytes()[2:]
            self.assertEqual(raw('first-clicks'), b'\0')
            self.assertEqual(raw('second-clicks'), b'\1')
            self.assertEqual(raw('reused-clicks'), b'\0')
            self.assertEqual(raw('names'), b'large'+bytes(11)+b'second'+bytes(10))
            for name in ('code0','code1','retained'):
                self.assertEqual(raw('before-full-'+name), raw('after-full-'+name))
            self.assertEqual(len(raw('two-generic-windows-bitmap')), 8000)
            self.assertEqual(raw('two-generic-windows-bitmap'), raw('two-generic-windows-shadow'))

    def test_legacy_native_input_and_clean_build_regressions(self):
        report = json.loads((R/'four-apps-vice-d64/result.json').read_text())
        self.assertEqual(report['disk_sha256'], digest(A/'udeks.d64'))
        for flag in ('four_apps','image_matches_disk','shadow_matches_bitmap'):
            self.assertTrue(report[flag])
        self.assertTrue(any(r.get('foreground_ctrl_c') for r in report['records']))
        self.assertTrue(any(r.get('desktop_closes_all') and r.get('software_guards_ok')
                            for r in report['records']))
        report = json.loads((R/'native-input-d64/result.json').read_text())
        self.assertEqual(report['disk_sha256'], digest(A/'udeks.d64'))
        self.assertEqual(report['test_disk_sha256'], digest(A/'native-test.d64'))
        self.assertEqual(report['exit_status'], 0)
        self.assertTrue(report['raw_iec'] and report['four_apps'])
        self.assertIn('PASS four apps: native input', (R/'native-input-d64/run.log').read_text())
        clean = json.loads((R/'clean-result.json').read_text())
        self.assertTrue(clean['byte_identical'])
        self.assertEqual(len(clean['sha256']), 9)
        for name, expected in clean['sha256'].items():
            artifact = 'storage-module.bin' if name=='storage/module.bin' else Path(name).name
            self.assertEqual(digest(A/artifact), expected, name)


if __name__ == '__main__': unittest.main()

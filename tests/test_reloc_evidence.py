# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from gen_capability_imports import map_exports
from o65_to_udex import pack_o65, relocate_executable

A = ROOT/'bench/artifacts/2026-10-04-relocatable-apps'
R = ROOT/'bench/results/2026-10-04-relocatable-apps'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RelocEvidence(unittest.TestCase):
    def test_preserved_hashes_and_independent_flat_link_oracles(self):
        for folder in (A, R):
            for line in (folder/'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertEqual(digest(folder/name), expected, name)
        executable = (A/'relocapp.udx').read_bytes()
        entry = map_exports((A/'probe.map').read_text())['_udeks_program_entry'][0]
        self.assertEqual(pack_o65((A/'probe.o65').read_bytes(), entry), executable)
        self.assertEqual(len(executable), 1175)
        for base, capacity in ((0x2300, 0x1200), (0x3500, 0xb00)):
            self.assertEqual(relocate_executable(executable, base, capacity),
                             (A/f'oracle-{base:04x}.udx').read_bytes())

    def test_one_disk_file_runs_in_two_slots_and_reloads_cleanly(self):
        executable = (A/'relocapp.udx').read_bytes()
        for suffix, drive in (('d64', '1541'), ('d71', '1571')):
            folder = R/('vice-'+suffix)
            result = json.loads((folder/'result.json').read_text())
            self.assertEqual(result['drive'], drive)
            self.assertEqual(result['disk_sha256'], digest(A/('reloc-test.'+suffix)))
            self.assertEqual(result['loader_sha256'], digest(A/'banked-loader.bin'))
            self.assertTrue(result['relocatable_same_file'])
            self.assertEqual(result['relocatable_sha256'], digest(A/'relocapp.udx'))
            self.assertTrue(result['console_alive'])
            self.assertTrue(result['legacy_code_preserved'])
            tasks = [r for r in result['records'] if 'native_task' in r]
            self.assertEqual([r['native_task'] for r in tasks], [3, 4, 3])
            for record in tasks:
                self.assertGreaterEqual(record['progress'], 8)
                self.assertEqual(record['value'], (3000+3*record['progress']) & 65535)
                self.assertEqual(record['exit_status'], 43)
                self.assertTrue(record['guards_ok'])
            for tag, base, capacity in ((3, 0x2300, 0x1200), (4, 0x3500, 0xb00)):
                image = relocate_executable(executable, base, capacity)
                bss = int.from_bytes(image[12:14], 'little')
                expected = image[16:] + bytes(bss)
                self.assertEqual((folder/f'app{tag}.bin').read_bytes()[2:2+len(expected)], expected)
                self.assertEqual((folder/f'native{tag}-error.bin').read_bytes()[2:], b'\0')
                for name, size in (('bottom',16), ('top',16), ('cpu-stack',1)):
                    self.assertEqual((folder/f'native{tag}-{name}.bin').read_bytes()[2:], b'\xa5'*size)
                for name, size in (('task',8), ('context',11)):
                    self.assertEqual((folder/f'reaped-{name}{tag}.bin').read_bytes()[2:], bytes(size))
            calls = [r for r in result['records'] if 'selector' in r]
            for call in calls:
                self.assertTrue(call['request_preserved'])
                self.assertTrue(call['kernel_map_restored'])
            for name in ('rcount','rpast','rdup','rorder','rbase','rentry','rflags','rshort','rtrail'):
                self.assertIn((3, name, 8), [(r['selector'],r['name'],r['errno']) for r in calls])
            for name in ('clock-code', 'wave-code', 'z80-code'):
                self.assertEqual((folder/(name+'.bin')).read_bytes(),
                                 (folder/('after-'+name+'.bin')).read_bytes())

    def test_existing_four_graphical_apps_still_work(self):
        folder = R/'four-apps-vice-d64'
        report = json.loads((folder/'result.json').read_text())
        self.assertEqual(report['disk_sha256'], digest(A/'udeks.d64'))
        for flag in ('four_apps','image_matches_disk','shadow_matches_bitmap'):
            self.assertTrue(report[flag])
        self.assertTrue(any(r.get('desktop_closes_all') and r.get('software_guards_ok')
                            for r in report['records']))
        self.assertTrue(any(r.get('foreground_ctrl_c') for r in report['records']))
        self.assertEqual((folder/'four-apps-bitmap.bin').read_bytes()[2:],
                         (folder/'four-apps-shadow.bin').read_bytes()[2:])

    def test_native_input_regression_and_clean_build(self):
        folder = R/'native-input-d64'
        report = json.loads((folder/'result.json').read_text())
        self.assertEqual(report['disk_sha256'], digest(A/'udeks.d64'))
        self.assertEqual(report['test_disk_sha256'], digest(A/'native-test.d64'))
        self.assertEqual(report['exit_status'], 0)
        self.assertTrue(report['raw_iec'])
        self.assertTrue(report['four_apps'])
        self.assertIn('PASS four apps: native input', (folder/'run.log').read_text())
        clean = json.loads((R/'clean-result.json').read_text())
        self.assertTrue(clean['byte_identical'])
        for name in ('boot/udeks.d64','boot/udeks.d71','boot/banked-loader.bin',
                     'boot/banked-reloc.bin','boot/banked-access.bin','boot/task-lookup.bin',
                     'storage/module.bin','generic-apps/relocapp.udx'):
            self.assertEqual(clean['sha256'][name], digest(A/Path(name).name))

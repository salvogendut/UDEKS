# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from add_disk_apps import add_apps
from native_worker_probe import expected_surface,expected_wave
from o65_to_udex import relocate_executable
A=ROOT/'bench/artifacts/2026-10-04-native-worker'
R=ROOT/'bench/results/2026-10-04-native-worker'

def digest(data): return hashlib.sha256(data).hexdigest()

class NativeWorkerEvidence(unittest.TestCase):
    def test_hashes_and_fixture_identity(self):
        for directory in (A,R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                checksum,name=line.split()
                self.assertEqual(digest((directory/name).read_bytes()),checksum,name)
        program=(A/'WORKER.BIN').read_bytes()
        self.assertEqual(len(program),920)
        self.assertLessEqual(sum(int.from_bytes(program[n:n+2],'little') for n in (10,12)),2816)
        for suffix in ('d64','d81'):
            report=json.loads((R/('vice-'+suffix)/'result.json').read_text())
            disk=(A/('udeks.'+suffix)).read_bytes()
            self.assertEqual(report['disk_sha256'],digest(disk))
            self.assertEqual(report['program_sha256'],digest(program))
            self.assertEqual(report['fixture_sha256'],digest(add_apps(disk,[('WORKER.BIN',program),('PEER.BIN',program)])))

    def test_both_private_math_results_and_relocated_images(self):
        program=(A/'WORKER.BIN').read_bytes()
        for suffix in ('d64','d81'):
            directory=R/('vice-'+suffix); report=json.loads((directory/'result.json').read_text())
            self.assertEqual(report['slots'],[3,4])
            for key in ('surface_oracle','wave_oracle','private_results','sequence_checked','errors_return',
                        'lease_counts','console_live','lazy_graphics','legacy_coexistence','reap_reload','stack_guards'):
                self.assertTrue(report[key])
            for row in report['records']:
                if 'check' not in row: continue
                tag=row['check']
                self.assertEqual((directory/(tag+'-samples.bin')).read_bytes()[2:],expected_surface())
                self.assertEqual((directory/(tag+'-wave.bin')).read_bytes()[2:],expected_wave(row['phase']))
                self.assertEqual(row['steps'],21)
                base,capacity=(0x2300,0x1200) if row['slot']==3 else (0x3500,0xb00)
                self.assertEqual((directory/(tag+'-code.bin')).read_bytes()[2:],
                                 relocate_executable(program,base,capacity)[16:])
            before=(directory/'engine-before.bin').read_bytes()[2:]
            after=(directory/'engine-after.bin').read_bytes()[2:]
            self.assertEqual(int.from_bytes(after[12:14],'little')-int.from_bytes(before[12:14],'little'),46)
            self.assertEqual(int.from_bytes(after[14:16],'little')-int.from_bytes(before[14:16],'little'),2)
            self.assertFalse(any((directory/'fresh-bss.bin').read_bytes()[2:]))
            self.assertEqual((directory/'reload-reaped.bin').read_bytes()[2:],b'\0')

    def test_clock_resize_and_four_app_regression_used_same_kernel(self):
        report=json.loads((R/'resize-regression.json').read_text())
        self.assertEqual(report['disk_sha256'],digest((A/'udeks.d71').read_bytes()))
        self.assertEqual(report['program_sha256'],digest((A/'NCLOCK.BIN').read_bytes()))
        for key in ('resize','drag','targeted_ctrl_c','four_app_compatibility','stack_guards','running_panel'):
            self.assertTrue(report[key])

if __name__=='__main__': unittest.main()

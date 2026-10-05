# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from add_disk_apps import add_apps
from gen_capability_imports import map_exports
from native_clock_probe import clock_commands
from o65_to_udex import pack_o65,relocate_executable

A=ROOT/'bench/artifacts/2026-10-04-native-clock'
R=ROOT/'bench/results/2026-10-04-native-clock'
BASE=ROOT/'bench/artifacts/2026-10-04-console-d81'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeClockEvidence(unittest.TestCase):
    def test_artifact_hashes_image_size_and_independent_packing(self):
        for folder in (A,R):
            for row in (folder/'SHA256SUMS').read_text().splitlines():
                expected,name=row.split()
                self.assertEqual(digest(folder/name),expected,name)
        program=(A/'NCLOCK.BIN').read_bytes()
        self.assertEqual(program[:8],b'UDEX\0\2\1\0')
        self.assertEqual((len(program),int.from_bytes(program[10:12],'little'),
                          int.from_bytes(program[12:14],'little')),(2463,2039,351))
        symbols=map_exports((A/'xclock_native.map').read_text())
        self.assertEqual(pack_o65((A/'xclock_native.o65').read_bytes(),
                                 symbols['_udeks_program_entry'][0]),program)

    def test_three_format_native_execution_and_retained_model(self):
        program=(A/'NCLOCK.BIN').read_bytes()
        for suffix,drive in (('d64','1541'),('d71','1571'),('d81','1581')):
            folder=R/('vice-'+suffix)
            report=json.loads((folder/'result.json').read_text())
            self.assertEqual(report['drive'],drive)
            self.assertEqual(report['disk_sha256'],digest(BASE/('udeks.'+suffix)))
            self.assertEqual(report['fixture_sha256'],digest(A/('native-clock.'+suffix)))
            self.assertEqual(report['program_sha256'],digest(A/'NCLOCK.BIN'))
            self.assertEqual(add_apps((BASE/('udeks.'+suffix)).read_bytes(),
                [('NCLOCK.BIN',program),('CLOCK2.BIN',program)]),
                (A/('native-clock.'+suffix)).read_bytes())
            for field in ('relocated_code','commands_oracle','date_updates','drag',
                          'targeted_ctrl_c','reload','legacy_state_untouched',
                          'four_app_compatibility','stack_guards'):
                self.assertTrue(report[field],field)
            seen=set()
            for row in report['records']:
                if 'check' not in row: continue
                tag=row['check']; slot=row['slot']; seen.add(slot)
                base,capacity=(0x2300,0x1200) if slot==3 else (0x3500,0xb00)
                self.assertEqual((folder/(tag+'-code.bin')).read_bytes()[2:],
                                 relocate_executable(program,base,capacity)[16:])
                expected=clock_commands(row['hour'],row['minute'])
                for kind in ('commands','retained'):
                    self.assertEqual((folder/(tag+'-'+kind+'.bin')).read_bytes()[2:],expected)
                self.assertEqual((folder/(tag+'-time.bin')).read_bytes()[2:],
                                 bytes((row['hour'],row['minute'],row['presents'])))
            self.assertEqual(seen,{3,4})
            self.assertEqual((folder/'legacy-before.bin').read_bytes(),
                             (folder/'legacy-after.bin').read_bytes())
            self.assertEqual((folder/'two-native-clocks-shadow.bin').read_bytes()[2:],
                             (folder/'two-native-clocks-bitmap.bin').read_bytes()[2:])
            checks={row['check']:row for row in report['records'] if 'check' in row}
            for tag in ('first-changed-time','second-changed-time'):
                self.assertEqual((checks[tag]['hour'],checks[tag]['minute']),(21,45))
            self.assertEqual(checks['reloaded-clock']['presents'],1)

    def test_unmodified_1986_native_input(self):
        report=json.loads((R/'1986-d64/result.json').read_text())
        self.assertEqual(report['exit_status'],0)
        self.assertEqual(report['disk_sha256'],digest(BASE/'udeks.d64'))
        self.assertEqual(report['test_disk_sha256'],digest(A/'native-clock.d64'))
        self.assertEqual(report['program_sha256'],digest(A/'NCLOCK.BIN'))
        self.assertTrue(report['native_clock'] and report['raw_iec'])
        self.assertIn('PASS native clock: both slots, date, native drag/close, Ctrl+C, reload, four windows, console, guards, bitmap',
                      (R/'1986-d64/run.log').read_text())


if __name__=='__main__': unittest.main()

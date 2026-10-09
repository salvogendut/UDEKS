# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from add_disk_apps import add_apps
from native_app_layout import ALLOCATIONS, fitting_allocations
from o65_to_udex import relocate_executable

A=ROOT/'bench/results/2026-10-09-native-console'


class NativeConsoleEvidence(unittest.TestCase):
    def test_artifacts_are_intact_and_fixtures_only_add_disk_apps(self):
        for line in (A/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1)
            self.assertEqual(hashlib.sha256((A/name).read_bytes()).hexdigest(),digest,name)
        program=(A/'TICKER.BIN').read_bytes()
        self.assertEqual(fitting_allocations(program),[3,4,5,6])
        baseline=json.loads((A.parent/'2026-10-09-default-time/build.json').read_text())
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            original=(ROOT/f'bench/artifacts/2026-10-09-default-time-published/udeks.{fmt}').read_bytes()
            self.assertEqual(hashlib.sha256(original).hexdigest(),report['source_disk_sha256'])
            self.assertEqual(report['source_disk_sha256'],baseline['disks'][fmt]['sha256'])
            fixture=add_apps(original,[('TICKER.BIN',program),('PULSE.BIN',program)])
            self.assertEqual(hashlib.sha256(fixture).hexdigest(),report['fixture_sha256'])
            self.assertEqual(hashlib.sha256(program).hexdigest(),report['program_sha256'])

    def test_raw_code_private_state_guards_and_reuse(self):
        _,base,limit,_,_,_=next(row for row in ALLOCATIONS if row[0]==6)
        installed=relocate_executable((A/'TICKER.BIN').read_bytes(),base,limit-base)[16:]
        for fmt in ('d64','d81'):
            def data(name): return (A/fmt/(name+'.bin')).read_bytes()[2:]
            for tag in ('solo','with-clock'):
                self.assertEqual(data(tag+'-code'),installed)
                self.assertEqual(data(tag+'_ticker_private'),b'1234')
                self.assertEqual(data(tag+'_ticker_failure'),b'\0')
                for offset in (0,176):
                    self.assertEqual(data(tag+'-guard-'+str(offset)),b'\xa5'*16)
            self.assertEqual(data('reaped'),b'\0')
            self.assertEqual(data('ticker-step'),b'\6')
            self.assertEqual(data('prompt'),b'\4\2')
            self.assertEqual(data('vic-before'),data('vic-after'))
            self.assertNotEqual(data('clock-deadline'),data('clock-deadline-after'))

    def test_console_and_concurrent_drag_without_overclaiming_job_control(self):
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            for key in ('arguments','stdin','background_policy','shell_exit_status'):
                self.assertFalse(report[key])
            self.assertTrue(report['source_disk_unchanged'])
            expected='ticker: native task started\nticker: stderr works\n'+''.join(
                'tick '+str(n)+'\n' for n in range(1,6))+'ticker: complete'
            for tag in ('solo','with-clock'):
                record=next(r for r in report['records'] if r.get('check')==tag)
                self.assertIn(expected,record['console'])
            drag=next(r for r in report['records'] if r.get('check')=='clock-and-drag-during-console')
            self.assertIn(drag['ticker_step'],range(1,6))
            self.assertEqual(report['records'][-1]['command'],'xclock -q')


if __name__=='__main__': unittest.main()

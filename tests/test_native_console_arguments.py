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

A=ROOT/'bench/results/2026-10-09-native-console-arguments'


class NativeConsoleArguments(unittest.TestCase):
    def data(self,fmt,name):
        return (A/fmt/(name+'.bin')).read_bytes()[2:]

    def test_hashes_and_exact_fixture_reconstruction(self):
        manifest=(A/'SHA256SUMS').read_text().splitlines()
        names=[]
        for line in manifest:
            digest,name=line.split('  ',1); names.append(name)
            self.assertEqual(hashlib.sha256((A/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(set(names),{str(p.relative_to(A)) for p in A.rglob('*')
                                    if p.is_file() and p.name not in ('README.md','SHA256SUMS')})
        ticker=(A/'TICKER.BIN').read_bytes(); quiet=(A/'QUIET.BIN').read_bytes()
        for binary in (ticker,quiet): self.assertEqual(fitting_allocations(binary),[3,4,5,6])
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            source=(A/'build'/('udeks.'+fmt)).read_bytes()
            self.assertEqual(hashlib.sha256(source).hexdigest(),report['source_disk_sha256'])
            apps=[('TICKER.BIN',ticker),('QUIET.BIN',quiet)]
            if fmt=='d81': apps.append(('PULSE.BIN',ticker))
            self.assertEqual(hashlib.sha256(add_apps(source,apps)).hexdigest(),report['fixture_sha256'])
            self.assertEqual(hashlib.sha256(ticker).hexdigest(),report['program_sha256'])
            self.assertEqual(hashlib.sha256(quiet).hexdigest(),report['quiet_sha256'])
            self.assertTrue(report['source_disk_unchanged'])

    def assert_arguments(self,record,argv):
        self.assertEqual(len(record),81)
        self.assertEqual(record[:8],b'UARG\0\1'+bytes((len(argv),0)))
        end=26
        for i,arg in enumerate(argv):
            ptr=int.from_bytes(record[8+2*i:10+2*i],'little')
            self.assertTrue(0x9a<=ptr<=0xd0)
            start=ptr-0x80; encoded=arg.encode()+b'\0'
            self.assertEqual(record[start:start+len(encoded)],encoded)
            end=max(end,start+len(encoded))
        self.assertEqual(record[8+2*len(argv):26],bytes(18-2*len(argv)))
        self.assertEqual(record[end:],bytes(81-end))

    def test_raw_arguments_code_state_stack_guards_and_reuse(self):
        for fmt in ('d64','d81'):
            for tag,task,argv in (
                ('solo',6,['ticker','Alpha','mixed-case','37']),
                ('with-clock',5,['pulse' if fmt=='d81' else 'ticker','a','B','c','D','e','F','last'])):
                self.assert_arguments(self.data(fmt,tag+'-arguments'),argv)
                _,base,limit,_,_,_=next(row for row in ALLOCATIONS if row[0]==task)
                installed=relocate_executable((A/'TICKER.BIN').read_bytes(),base,limit-base)[16:]
                self.assertEqual(self.data(fmt,tag+'-code'),installed)
                self.assertEqual(self.data(fmt,tag+'_ticker_private'),b'1234')
                self.assertEqual(self.data(fmt,tag+'_ticker_failure'),b'\0')
                for offset in (0,176): self.assertEqual(self.data(fmt,tag+'-guard-'+str(offset)),b'\xa5'*16)
            self.assert_arguments(self.data(fmt,'quiet_arguments'),['quiet'])
            self.assertEqual(self.data(fmt,'quiet_failure'),b'\0')
            self.assertEqual(self.data(fmt,'quiet_stage'),b'\2')
            self.assertEqual(self.data(fmt,'reaped'),b'\0')
            self.assertEqual(self.data(fmt,'quiet-reaped'),b'\0')
            self.assertEqual(self.data(fmt,'prompt'),b'\4\2')
            self.assertEqual(self.data(fmt,'vic-before'),self.data(fmt,'vic-after'))
            self.assertNotEqual(self.data(fmt,'clock-deadline'),self.data(fmt,'clock-deadline-after'))

    def test_cpu_proof_and_bounds_match_current_sources(self):
        report=json.loads((A/'cpu/report.json').read_text())
        self.assertEqual(report['comparisons'],11520)
        self.assertTrue(report['argument_entry'])
        for name,digest in report['inputs'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
        self.assertIn('FAIL tokenizer',(A/'cpu/negative.log').read_text())
        self.assertIn('PASS argument copy/entry',(A/'cpu/entry.log').read_text())
        constants=(ROOT/'src/8502/native_args.inc').read_text()
        for key,value in (('NATIVE_ARGS_MAX',8),('NATIVE_ARGS_TEXT_SIZE',55)):
            self.assertRegex(constants,rf'{key}\s*=\s*{value}\b')
        self.assertRegex((ROOT/'include/udeks/line_editor.h').read_text(),r'UDEKS_LINE_EDITOR_CAPACITY\s+54u')
        self.assertRegex((ROOT/'include/udeks/shell.h').read_text(),r'UDEKS_SHELL_MAX_ARGUMENTS\s+8u')

    def test_exit_status_and_concurrency_reports_keep_scope_honest(self):
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            self.assertTrue(report['arguments']); self.assertTrue(report['shell_exit_status'])
            self.assertFalse(report['stdin']); self.assertFalse(report['background_policy'])
            statuses=[r['console'].splitlines()[-2] for r in report['records'] if r.get('command')=='echo $?']
            self.assertEqual(statuses,['37','0','2'])
            drag=next(r for r in report['records'] if r.get('check')=='clock-and-drag-during-console')
            self.assertIn(drag['ticker_step'],range(1,6))
            peer=next(r for r in report['records'] if r.get('check')=='distinct-private-arguments')
            self.assertEqual(peer['foreground_exit'],37)
        service=json.loads((A/'regressions/1986-service.json').read_text())
        self.assertEqual(service['exit_status'],0); self.assertTrue(service['disk_service'])
        self.assertEqual(service['disk_sha256'],hashlib.sha256((A/'build/udeks.d64').read_bytes()).hexdigest())
        graphics=json.loads((A/'regressions/four-native.json').read_text())
        self.assertEqual(graphics['disk_sha256'],hashlib.sha256((A/'build/udeks.d81').read_bytes()).hexdigest())
        self.assertEqual(graphics['checks'][-1]['command'],'echo four-slot cleanup passed')


if __name__=='__main__': unittest.main()

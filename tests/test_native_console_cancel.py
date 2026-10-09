# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from add_disk_apps import add_apps
from build_scheduler_overlay import map_segments
from native_app_layout import fitting_allocations

A=ROOT/'bench/results/2026-10-09-native-console-cancel'


class NativeConsoleCancel(unittest.TestCase):
    def data(self,fmt,name): return (A/fmt/(name+'.bin')).read_bytes()[2:]

    def test_evidence_hashes_and_disposable_fixtures(self):
        names=[]
        for line in (A/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1); names.append(name)
            self.assertEqual(hashlib.sha256((A/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(set(names),{str(p.relative_to(A)) for p in A.rglob('*')
                                   if p.is_file() and p.name not in ('README.md','SHA256SUMS')})
        nap=(A/'NAP.BIN').read_bytes(); ticker=(A/'TICKER.BIN').read_bytes()
        self.assertEqual(fitting_allocations(nap),[3,4,5,6])
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            base=(A/'build'/('udeks.'+fmt)).read_bytes()
            self.assertEqual(hashlib.sha256(base).hexdigest(),report['source_disk_sha256'])
            fixture=add_apps(base,[('NAP.BIN',nap),('TICKER.BIN',ticker)])
            self.assertEqual(hashlib.sha256(fixture).hexdigest(),report['fixture_sha256'])
            for name,data in (('nap',nap),('ticker',ticker)):
                self.assertEqual(hashlib.sha256(data).hexdigest(),report[name+'_sha256'])

    def test_all_slots_reaped_waits_cleared_without_retiring_peers(self):
        wait_fields=('state','operation','sequence','descriptor','count','flags',
                     'selector','selector_high','child','status')
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            cancels=[r for r in report['checks'] if 'task' in r]
            self.assertEqual([r['task'] for r in cancels],[6,5,3,4,4])
            for row in cancels:
                tag=row['check']
                self.assertEqual(self.data(fmt,tag+'-before')[:3],bytes((1,4,3)))
                self.assertEqual(self.data(fmt,tag+'-after'),bytes(8))
                self.assertEqual(self.data(fmt,tag+'-owned'),b'\0')
                for field in wait_fields: self.assertEqual(self.data(fmt,tag+'-wait-'+field),b'\0')
                before=self.data(fmt,tag+'-generation-before')[0]
                self.assertEqual(self.data(fmt,tag+'-generation-after'),bytes(((before+1)&255,)))
                for peer in row['peers']:
                    self.assertEqual(self.data(fmt,tag+'-peer'+str(peer)+'-before'),
                                     self.data(fmt,tag+'-peer'+str(peer)+'-after'))
                if tag!='clock':
                    self.assertEqual(self.data(fmt,tag+'-steps-before'),self.data(fmt,tag+'-steps-after'))
                self.assertEqual(row['status'],130)
                self.assertTrue(row['console'].endswith('echo $?\n130\nUDEKS:~>'))
            self.assertEqual(self.data(fmt,'idle-generations-before'),self.data(fmt,'idle-generations-after'))

    def test_old_sleep_never_resumes_and_reuse_returns_normal_exit(self):
        for fmt in ('d64','d81'):
            self.assertEqual(self.data(fmt,'retired-steps-before'),self.data(fmt,'retired-steps-after'))
            self.assertGreater(int.from_bytes(self.data(fmt,'retired-steps-before'),'little'),0)
            elapsed=(int.from_bytes(self.data(fmt,'ticks-after'),'little')-
                     int.from_bytes(self.data(fmt,'ticks-before'),'little'))&65535
            self.assertGreaterEqual(elapsed,620)
            self.assertEqual(self.data(fmt,'vic-before'),self.data(fmt,'vic-after'))
            report=json.loads((A/fmt/'report.json').read_text())
            self.assertIn({'check':'reuse-natural-exit','status':37},report['checks'])
            self.assertFalse(report['stdin']); self.assertFalse(report['background_policy'])

    def test_actual_layout_and_native_input_regression(self):
        for filename in ('udeks-8502.map','udeks-8502-panic-probe.map'):
            seg=map_segments((A/'build'/filename).read_text())
            self.assertEqual(seg['BSS'][1],0x93c4)
            self.assertEqual(seg['SERVICEBOOT'][0],0x93d0)
        seg=map_segments((A/'build/banked-loader.map').read_text())
        self.assertEqual([seg[name][1] for name in ('CODE','RELOC','ACCESS')],[0xdff4,0x19ed,0x1ffe])
        ush=map_segments((A/'build/ush.map').read_text())
        self.assertEqual(ush['BSS'][1],0x9f44)
        self.assertLess(ush['BSS'][0]+368,0xa000)
        report=json.loads((A/'1986/result.json').read_text())
        self.assertEqual(report['exit_status'],0); self.assertTrue(report['four_native'])
        self.assertEqual(report['disk_sha256'],hashlib.sha256((A/'build/udeks.d64').read_bytes()).hexdigest())
        self.assertIn('PASS four native:',(A/'1986/run.log').read_text())


if __name__=='__main__': unittest.main()

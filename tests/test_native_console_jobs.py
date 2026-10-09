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
from native_app_layout import ALLOCATIONS
from o65_to_udex import relocate_executable

A=ROOT/'bench/results/2026-10-09-native-console-jobs'


class NativeConsoleJobsEvidence(unittest.TestCase):
    def test_manifest_and_reconstructed_media(self):
        names=set()
        for line in (A/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1); names.add(name)
            self.assertEqual(hashlib.sha256((A/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(names,{str(p.relative_to(A)) for p in A.rglob('*')
                              if p.is_file() and p.name not in ('README.md','SHA256SUMS')})
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            names=('ASK','TICKER') if fmt=='d64' else ('ASK','BGREAD','TICKER')
            apps={n:(A/(n+'.BIN')).read_bytes() for n in names}
            source=(A/'build'/('udeks.'+fmt)).read_bytes()
            self.assertEqual(report['source_disk_sha256'],hashlib.sha256(source).hexdigest())
            self.assertEqual(report['fixture_sha256'],hashlib.sha256(add_apps(source,
                [(n+'.BIN',data) for n,data in apps.items()])).hexdigest())
            self.assertEqual(report['apps'],{n:hashlib.sha256(d).hexdigest() for n,d in apps.items()})

    def test_completed_scenarios_code_guards_and_draft(self):
        program=(A/'TICKER.BIN').read_bytes()
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            checks=report['checks']
            self.assertEqual([r['check'] for r in checks],
                ['shell-edit','application-edit','background-after-cancel'])
            self.assertEqual(checks[0]['argv'],['ticker','a','B','c','D','e','F','last'])
            self.assertEqual(checks[1]['argv'],['ticker','Mixed-case','while-reading'])
            self.assertTrue(checks[0]['console'].endswith('UDEKS:~> echo drft'))
            self.assertTrue(checks[1]['console'].endswith('input kept'))
            self.assertIn('tick 5\nticker: complete',checks[0]['console'])
            for row in checks:
                tag=row['check']
                _,base,limit,stack,_,_=next(a for a in ALLOCATIONS if a[0]==row['task'])
                self.assertEqual((A/fmt/(tag+'-code.bin')).read_bytes()[2:],
                    relocate_executable(program,base,limit-base)[16:])
                for offset in (0,0xb0):
                    self.assertEqual((A/fmt/(tag+'-guard-'+str(offset)+'.bin')).read_bytes()[2:],b'\xa5'*16)
                raw=(A/fmt/(tag+'-console.bin')).read_bytes()[2:]
                screen='\n'.join(raw[i:i+64].decode('ascii',errors='replace').rstrip()
                                 for i in range(0,1365,65))
                self.assertEqual(screen,row['console'])
            for tag in ('draft-before','draft-after'):
                raw=(A/fmt/(tag+'.bin')).read_bytes()[2:]
                self.assertEqual(raw[1365:],bytes((16,20,1))) # prompt 9 + edit cursor 7
            self.assertTrue(all(report[k] for k in ('foreground_input','history','cancellation','exit_status')))
            self.assertEqual(report['background_read_errno'],None if fmt=='d64' else 5)

    def test_fixed_layout_and_native_1986_regression(self):
        for name in ('udeks-8502.map','udeks-8502-panic-probe.map'):
            seg=map_segments((A/'build'/name).read_text())
            self.assertEqual(seg['BSS'][1],0x93a7)
            self.assertEqual(seg['HIGHBSS'][1],0xe2e0)
            self.assertEqual(seg['TASKREQUEST'][1],0xf8f6)
            self.assertEqual(seg['VICSHADOW'][:2],(0xa1e0,0xc11f))
        self.assertEqual(map_segments((A/'build/udeks-scheduler-overlay.map').read_text())['BSS'][1],0xc862)
        report=json.loads((A/'1986/result.json').read_text())
        self.assertEqual(report['exit_status'],0)
        self.assertTrue(report['four_native'])
        self.assertEqual(report['disk_sha256'],hashlib.sha256((A/'build/udeks.d64').read_bytes()).hexdigest())
        self.assertIn('PASS four native:',(A/'1986/run.log').read_text())


if __name__=='__main__': unittest.main()

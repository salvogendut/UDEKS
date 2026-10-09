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
from gen_capability_imports import map_exports
from native_app_layout import fitting_allocations

A=ROOT/'bench/results/2026-10-09-native-console-input'


class NativeConsoleInputEvidence(unittest.TestCase):
    def test_manifest_and_exact_media(self):
        names=set()
        for line in (A/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1); names.add(name)
            self.assertEqual(hashlib.sha256((A/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(names,{str(p.relative_to(A)) for p in A.rglob('*')
                               if p.is_file() and p.name not in ('README.md','SHA256SUMS')})
        apps={n:(A/(n+'.BIN')).read_bytes() for n in ('ASK','BGREAD')}
        for image in apps.values(): self.assertEqual(fitting_allocations(image),[3,4,5,6])
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            source=(A/'build'/('udeks.'+fmt)).read_bytes()
            self.assertEqual(report['source_disk_sha256'],hashlib.sha256(source).hexdigest())
            self.assertEqual(report['fixture_sha256'],hashlib.sha256(add_apps(source,
                [(name+'.BIN',image) for name,image in apps.items()])).hexdigest())
            self.assertEqual(report['apps'],{n:hashlib.sha256(d).hexdigest() for n,d in apps.items()})

    def test_all_four_slots_input_empty_full_edit_cancel_and_background(self):
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            reads=[r for r in report['checks'] if r['check']=='input']
            self.assertEqual({r['task'] for r in reads},{3,4,5,6})
            self.assertIn('',[r['text'] for r in reads])
            self.assertIn('edit me',[r['text'] for r in reads])
            self.assertEqual(max(len(r['text']) for r in reads),54)
            for row in reads:
                self.assertEqual((A/fmt/(row['tag']+'-waiting.bin')).read_bytes()[3:5],b'\4\2')
                self.assertEqual((A/fmt/(row['tag']+'-reaped.bin')).read_bytes()[2:],bytes(8))
                self.assertTrue(row['console'].endswith('echo $?\n0\nUDEKS:~>'))
            self.assertEqual([r['status'] for r in report['checks'] if r['check']=='cancel'],[130,130])
            self.assertIn(dict(check='background-denial',tasks=[4,6],errno=5,raw_read=True,poll=True),report['checks'])
            for field in ('state','operation','sequence','descriptor','count','flags',
                          'selector','selector_high','child','status'):
                self.assertEqual((A/fmt/('cancel-'+field+'.bin')).read_bytes()[2:],b'\0')
            self.assertEqual((A/fmt/'vic-before.bin').read_bytes(),(A/fmt/'vic-after.bin').read_bytes())

    def test_actual_link_budgets_and_trusted_query(self):
        for filename in ('udeks-8502.map','udeks-8502-panic-probe.map'):
            seg=map_segments((A/'build'/filename).read_text())
            self.assertEqual(seg['BSS'][1],0x93ce)
            self.assertEqual(seg['SERVICEBOOT'][0],0x93d0)
            self.assertEqual(seg['MODULERODATA'][1],0xe631)
            self.assertEqual(seg['TASKREQUEST'][1],0xf907)
        scheduler=(A/'build/udeks-scheduler-overlay.map').read_text()
        self.assertEqual(map_segments(scheduler)['BSS'][1],0xc862)
        current=map_exports(scheduler)['_udeks_lifecycle_current_private'][0]
        router=(A/'build/router.bin').read_bytes()
        self.assertEqual(len(router),128)
        self.assertEqual(router[124:],b'\xad'+current.to_bytes(2,'little')+b'\x60')

    def test_cpu_negative_control_and_native_input_regression(self):
        cpu=json.loads((A/'cpu/report.json').read_text())
        self.assertEqual(cpu['ownership_cases'],2048)
        self.assertEqual(cpu['reader_cases'],6270)
        self.assertIn('FAIL owner',(A/'cpu/negative.log').read_text())
        self.assertIn('PASS 2048 owner checks',(A/'cpu/positive.log').read_text())
        emu=json.loads((A/'1986/result.json').read_text())
        self.assertEqual(emu['exit_status'],0); self.assertTrue(emu['four_native'])
        self.assertEqual(emu['disk_sha256'],hashlib.sha256((A/'build/udeks.d64').read_bytes()).hexdigest())
        self.assertIn('PASS four native:',(A/'1986/run.log').read_text())


if __name__=='__main__': unittest.main()

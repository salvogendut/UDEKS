# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from add_disk_apps import add_apps
from bench_decode import extract_memory
from build_scheduler_overlay import map_segments
from native_app_layout import ALLOCATIONS,fitting_allocations,check_linked_tables
from gen_capability_imports import map_exports
from native_clock_probe import clock_commands
from native_wave_probe import wave_paths
from native_worker_probe import expected_surface
from o65_to_udex import relocate_executable

A=ROOT/'bench/artifacts/2026-10-05-four-native'
R=ROOT/'bench/results/2026-10-05-four-native'
def digest(data): return hashlib.sha256(data).hexdigest()
def raw(directory,name): return (directory/(name+'.bin')).read_bytes()[2:]


class FourNativeEvidence(unittest.TestCase):
    def test_exact_artifacts_and_installed_fixtures(self):
        for directory in (A,R):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                checksum,name=line.split()
                self.assertEqual(digest((directory/name).read_bytes()),checksum,name)
        example=(A/'HELLO.BIN').read_bytes()
        self.assertEqual(fitting_allocations(example),[3,4,5,6])
        bad=bytearray(example);bad[-1]=255
        files=[(name+'.BIN',example) for name in ('ORBIT','CANVAS','HELLO','FOURTH','EXTRA')]+[('BADPATCH.BIN',bytes(bad))]
        for suffix in ('d64','d71','d81'):
            report=json.loads((R/('vice-'+suffix)/'result.json').read_text())
            disk=(A/('udeks.'+suffix)).read_bytes()
            self.assertEqual(report['disk_sha256'],digest(disk))
            self.assertEqual(report['fixture_sha256'],digest(add_apps(disk,files)))

    def test_all_default_and_unknown_instances_keep_code_and_stacks(self):
        example=(A/'HELLO.BIN').read_bytes()
        data=map_segments((A/'xhello.map').read_text())['DATA'][0]-0x1000
        defaults={3:'xcalc',4:'xclock',5:'xwave',6:'xdraw'}
        for suffix in ('d64','d71','d81'):
            directory=R/('vice-'+suffix)
            for tag in ('four','after-console','reloaded','unknown-four','unknown-reused'):
                for task,base,limit,stack,zp,hp in ALLOCATIONS:
                    program=example if tag.startswith('unknown') else (A/(defaults[task]+'.udx')).read_bytes()
                    code=relocate_executable(program,base,limit-base)[16:]
                    if tag.startswith('unknown'): code=code[:data]
                    self.assertEqual(raw(directory,tag+'-'+str(task)+'-code'),code)
                    for offset in (0,176):
                        self.assertEqual(raw(directory,f'{tag}-{task}-guard-{offset}'),b'\xa5'*16)
                lengths=raw(directory,tag+'-lengths')
                self.assertEqual(len(lengths),8)
                self.assertLessEqual(sum(int.from_bytes(lengths[i:i+2],'little')&0x7fff for i in range(0,8,2)),2304)

    def test_rendering_worker_resize_and_live_panel_oracles(self):
        for suffix in ('d64','d71','d81'):
            directory=R/('vice-'+suffix)
            report=json.loads((directory/'result.json').read_text())
            checks=[row for row in report['checks'] if 'check' in row]
            waves=[row for row in checks if 'presents' in row]
            self.assertEqual([row['presents'] for row in waves],[1,1,1,2,2,3,1])
            for tag,width,height in (('initial-wave',176,112),('moved-wave',176,112),
                                     ('before-resize',256,146),('resized-wave',176,112),('reloaded-wave',176,112)):
                self.assertEqual(raw(directory,tag+'-retained'),wave_paths(width,height)[0])
                self.assertEqual(raw(directory,tag+'-samples'),expected_surface())
            self.assertEqual(raw(directory,'held-presents'),bytes((2,)))
            initial=int.from_bytes(raw(directory,'leases-initial'),'little')
            self.assertEqual((initial-int.from_bytes(raw(directory,'leases-boot'),'little'))&65535,21)
            self.assertEqual(raw(directory,'leases-initial'),raw(directory,'leases-after-resizes'))
            self.assertEqual(raw(directory,'clock-retained'),clock_commands(3,15))
            self.assertEqual(raw(directory,'calc-46'),(4600).to_bytes(4,'little'))
            self.assertEqual(raw(directory,'draw-cell'),b'\1'+bytes(23))
            for tag in ('four-defaults','unknown-four'):
                self.assertEqual(raw(directory,tag+'-shadow'),raw(directory,tag+'-bitmap'))
            for row in checks:
                if not row['check'].endswith('-panel'): continue
                tag=row['check'][:-6]
                names=['xinit']+[row['names'][str(task)] for task in (3,4,5,6)]
                for i,name in enumerate(names,2):
                    expected=bytes(ord(c.upper())&31 if c.isalpha() else ord(c) for c in name[:9]).ljust(9,b' ')
                    self.assertEqual(raw(directory,f'{tag}-panel-{i}'),expected)
                    self.assertEqual(raw(directory,f'{tag}-attr-{i}'),bytes((128,))*9)

    def test_1986_native_input_guards_and_layout(self):
        report=json.loads((R/'1986-d64/result.json').read_text())
        self.assertEqual(report['exit_status'],0)
        self.assertTrue(report['four_native']);self.assertTrue(report['raw_iec'])
        self.assertEqual(report['disk_sha256'],digest((A/'udeks.d64').read_bytes()))
        self.assertIn('PASS four native:',(R/'1986-d64/run.log').read_text())
        snapshot=(R/'1986-d64/result.vsf').read_bytes()
        for task,base,limit,stack,zp,hp in ALLOCATIONS:
            self.assertEqual(extract_memory(snapshot,0x10000+hp,1),b'\xa5')
            for offset in (0,176):
                self.assertEqual(extract_memory(snapshot,0x10000+stack+offset,16),b'\xa5'*16)
        self.assertEqual(extract_memory(snapshot,0xa1e0,8000),extract_memory(snapshot,0x16000,8000))
        text=(A/'udeks-8502.map').read_text()
        self.assertEqual(map_segments(text),map_segments((A/'udeks-8502-panic-probe.map').read_text()))
        check_linked_tables((A/'udeks-module.bin').read_bytes(),map_exports(text))

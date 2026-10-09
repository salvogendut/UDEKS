# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_d71 import validate_command,sector_offset
from build_scheduler_overlay import map_segments
from native_app_layout import ALLOCATIONS,fitting_allocations
from native_console_file_probe import make_fixture,PAYLOAD
from o65_to_udex import relocate_executable
from storage_public_probe import files

A=ROOT/'bench/results/2026-10-09-native-console-files'
PREVIOUS=ROOT/'bench/results/2026-10-09-native-console-jobs'


class NativeConsoleFileEvidence(unittest.TestCase):
    def test_manifest_and_only_cat_changes_on_shipped_disks(self):
        names=set()
        for line in (A/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1); names.add(name)
            self.assertEqual(hashlib.sha256((A/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(names,{str(p.relative_to(A)) for p in A.rglob('*')
                              if p.is_file() and p.name not in ('README.md','SHA256SUMS')})
        exe=(A/'CAT.BIN').read_bytes(); validate_command(exe)
        self.assertEqual(fitting_allocations(exe),[3,4,5])
        for fmt in ('d64','d81'):
            old=files((PREVIOUS/'build'/('udeks.'+fmt)).read_bytes())
            new=files((A/'build'/('udeks.'+fmt)).read_bytes())
            self.assertEqual(set(old),set(new))
            self.assertEqual([n for n in new if new[n]!=old[n]],[b'CAT.BIN'])
            self.assertEqual(new[b'CAT.BIN'],exe)
        disk=(A/'build/udeks.d64').read_bytes()
        self.assertEqual(sum(disk[sector_offset(18,0)+4*t] for t in range(1,36) if t!=18),16)
        self.assertEqual(files((A/'build/udeks.d71').read_bytes())[b'CAT.BIN'],exe)

    def test_reconstructed_media_and_file_persistence(self):
        for fmt in ('d64','d81'):
            report=json.loads((A/fmt/'report.json').read_text())
            apps={n:(A/(n+'.BIN')).read_bytes() for n in (() if fmt=='d64' else ('FHOLD','FRIVAL'))}
            source=(A/'build'/('udeks.'+fmt)).read_bytes()
            fixture=make_fixture(source,apps)
            self.assertEqual(report['source_disk_sha256'],hashlib.sha256(source).hexdigest())
            self.assertEqual(report['fixture_sha256'],hashlib.sha256(fixture).hexdigest())
            self.assertEqual(report['apps'],{n:hashlib.sha256(d).hexdigest() for n,d in apps.items()})
            audit=json.loads((A/fmt/'disk-audit.json').read_text())
            self.assertTrue(audit['existing_files_unchanged'])
            if fmt=='d64':
                self.assertEqual(audit['after_sha256'],report['fixture_sha256'])
                self.assertEqual(audit['created'],{})
            else:
                after=(A/fmt/'after.d81').read_bytes()
                self.assertEqual(audit['after_sha256'],hashlib.sha256(after).hexdigest())
                before_files=files(fixture); saved=files(after)
                for name,data in before_files.items(): self.assertEqual(saved[name],data)
                self.assertEqual({n:d for n,d in saved.items() if n not in before_files},
                                 {b'SAVED-EXIT':PAYLOAD,b'SAVED-CANCEL':PAYLOAD})

    def test_lifecycle_and_concurrent_clock_progress(self):
        for fmt in ('d64','d81'):
            checks=json.loads((A/fmt/'report.json').read_text())['checks']
            retired=[r for r in checks if 'cleanup' in r]
            self.assertEqual([r['check'] for r in retired],
                ([] if fmt=='d64' else ['foreign-read-write-close-open-denied','leaked-read-exit',
                                       'leaked-write-exit','leaked-write-cancel'])+['cat-read-cancel'])
            for r in retired:
                self.assertEqual(r['after'],(r['before']+1)&255)
                self.assertEqual(r['cleanup'],0)
            for command,status in (('cat /hello',0),('cat /empty',0),('cat /one',0),
                                   ('cat /nofile',1),('cat /',1),('cat',2),('cat /long',0)):
                found=[r for r in checks if r.get('command')==command]
                self.assertTrue(found,command)
                self.assertTrue(all(r['status']==status for r in found),command)
            self.assertIn('130',[r['console'] for r in checks if r.get('command')=='echo $?'][0])
            progress=next(r for r in checks if r.get('check')=='clock-progress-during-cat')
            for suffix,key in (('before','before'),('observed','after')):
                raw=(A/fmt/('clock-wait-'+suffix+'.bin')).read_bytes()[2:]
                self.assertEqual(progress[key],raw[0]+256*raw[8])
            self.assertNotEqual(progress['before'],progress['after'])
            self.assertEqual(checks[-1]['command'],'echo file-sdk-ok')

    def test_machine_code_private_state_and_stack_guards(self):
        for fmt in ('d64','d81'):
            cases=[('CAT',3,'cat-live',None),('CAT',3,'cat-complete',None)]
            if fmt=='d81': cases += [('FRIVAL',6,'rival',2),('FHOLD',4,'holder',3),
                                    ('FHOLD',6,'writer-exit',3),('FHOLD',6,'writer-cancel',2)]
            for name,task,tag,stage in cases:
                _,base,limit,_,_,_=next(row for row in ALLOCATIONS if row[0]==task)
                image=(A/(name+'.BIN')).read_bytes()
                self.assertEqual((A/fmt/(tag+'-code.bin')).read_bytes()[2:],
                                 relocate_executable(image,base,limit-base)[16:])
                for offset in (0,0xb0):
                    self.assertEqual((A/fmt/(tag+'-guard-'+str(offset)+'.bin')).read_bytes()[2:],b'\xa5'*16)
                state=(A/fmt/(tag+'-state.bin')).read_bytes()[2:]
                self.assertEqual(len(state),int.from_bytes(image[12:14],'little'))
                if stage is not None: self.assertEqual(state[:2],bytes((stage,0)))

    def test_no_resident_growth_and_native_1986_input(self):
        for name in ('udeks-8502.map','udeks-8502-panic-probe.map','udeks-scheduler-overlay.map'):
            self.assertEqual(map_segments((A/'build'/name).read_text()),
                             map_segments((PREVIOUS/'build'/name).read_text()))
        for mode,marker in (('1986','PASS native 1986 disk-service'),('1986-four','PASS four native:')):
            report=json.loads((A/mode/'result.json').read_text())
            self.assertEqual(report['exit_status'],0)
            self.assertTrue(report['disk_service' if mode=='1986' else 'four_native'])
            self.assertEqual(report['disk_sha256'],hashlib.sha256((A/'build/udeks.d64').read_bytes()).hexdigest())
            self.assertIn(marker,(A/mode/'run.log').read_text())
        log=(A/'1986/run.log').read_text()
        self.assertIn('command cat /hello:',log)
        self.assertIn('command cat /nofile:',log)
        self.assertIn('cat: No such file or directory',log)

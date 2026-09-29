# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from window_cache_acceptance import NAME, CASES, decode, negative, private_state
from window_cache_command import reference

def synthetic(case=0):
    data=bytearray(8096);data[:8]=b'AVLD\x01\x02'+bytes((case,0))
    rows,calls,images=(132,480,66) if case==0 else (312,337,2)
    data[8:10]=rows.to_bytes(2,'little');data[10:12]=calls.to_bytes(2,'little')
    data[12]=1;data[14]=images;data[22]=204;data[23]=15
    data[26]=2;data[30]=1;data[34]=2;data[38:64]=private_state(case)
    data[64:]=reference(case)
    return data

class WindowCacheAcceptanceTests(unittest.TestCase):
    def test_success_oracle_rejects_state_pixels_guards_and_incomplete_work(self):
        for case in (0,1):
            good=synthetic(case);decode(good,case)
            for i in list(range(38,64))+[0,4,5,6,7,8,10,14,15,16,17,18,19,20,21,23,26,30,34,36,37,64,8095]:
                bad=bytearray(good);bad[i]^=1
                with self.subTest(case=case,byte=i),self.assertRaises(ValueError):decode(bad,case)

    def test_rejection_requires_no_c_state_stack_or_pixel_activity(self):
        data=bytearray(8096);data[:8]=b'AVLD\x01\x02\0\0'
        data[10]=6;data[12]=1;data[22:24]=b'\xf0\x0f'
        data[26]=1;data[34]=1;data[38:64]=bytes([0x6d])*26
        for name in ('bad-code','bad-header'):
            negative(data,name)
            for i in [0,4,5,6,7,8,10,12,14,15,16,17,18,19,20,21,22,23,26,34,36,37,38,63,64,8095]:
                bad=bytearray(data);bad[i]^=1
                with self.subTest(name=name,byte=i),self.assertRaises(ValueError):negative(bad,name)

    def test_actual_live_runtime_faults_are_not_positive_passes(self):
        for name,fields in (('irq-leak',(15,)),('zp-leak',(16,)),('shell-stack',(19,21)),('no-pending',())):
            data=synthetic()
            for i in fields:data[i]=1
            if name=='shell-stack':data[22]=240
            if name=='no-pending':data[26]=1;data[30]=0;data[34]=0
            negative(data,name)
            with self.assertRaises(ValueError):decode(data,0)

    def test_charged_resident_budget_and_trusted_validation_before_c(self):
        archive=ROOT/'bench/artifacts'/NAME;build=archive/'build'
        report=json.loads((build/'build-report.json').read_text())
        self.assertEqual(report['objects']['raw']['CODE'],244)
        self.assertEqual(report['objects']['binding']['CODE'],309)
        self.assertEqual(report['objects']['validator']['GATEWAY'],79)
        self.assertEqual(report['resident_bytes'],553)
        self.assertEqual(report['remaining_before_hooks'],-51)
        self.assertEqual(report['module_bytes'],3977)
        self.assertEqual(report['page_calls'],16);self.assertEqual(report['last_page_bytes'],137)
        for obj in report['objects'].values():
            self.assertEqual(obj['BSS'],0);self.assertEqual(obj['ZEROPAGE'],0)
        validator=(archive/'bench/window-cache-acceptance/validator.s').read_text()
        self.assertNotIn('jsr',validator.lower())
        self.assertIn('cpy PARAM+3',validator)
        binding=(archive/'bench/window-cache-acceptance/binding.s').read_text()
        self.assertLess(binding.index('cmp #>CACHE_CHECKSUM'),binding.index('sta OP'))
        self.assertIn('cmp #$80\n        bne blocked\n        jsr _cache_raw_call',binding)
        driver=(build/'driver.s').read_text()
        self.assertIn('cpx #seed_end-seed\n        bcc install_seed',driver)
        self.assertIn('cpx #scan_end-scan\n        bcc install_scan',driver)
        probe=(build/'probe.c').read_text()
        self.assertIn('V(0xF780)=0xa5;V(0xF781)=0x5a;V(0xF782)=0xa5',probe)
        self.assertIn('V(0xF792)=4;W(0xF793)=0xbeef;V(0xF791)=0xff',probe)
        for key,root in (('source_sha256',archive),('linked_sha256',build),('program_sha256',build)):
            for n,sha in report[key].items():
                self.assertEqual(hashlib.sha256((root/n).read_bytes()).hexdigest(),sha,n)

    def test_preserved_two_emulator_provenance_and_one_byte_controls(self):
        build=ROOT/'bench/artifacts'/NAME/'build';results=ROOT/'bench/results'/NAME
        report=json.loads((build/'build-report.json').read_text())
        for group in ('negative_controls','rejection_controls'):
            for name,c in report[group].items():
                original=(build/(f'probe-{name}.original.prg' if group=='rejection_controls' else 'probe-0.prg')).read_bytes()
                bad=(build/f'probe-{name}.prg').read_bytes()
                self.assertEqual(len(original),len(bad))
                self.assertEqual([i for i,(a,b) in enumerate(zip(original,bad)) if a!=b],[c['offset']])
                self.assertEqual(original[c['offset']],c['before']);self.assertEqual(bad[c['offset']],c['after'])
        for engine in ('1986','vice'):
            record=json.loads((results/f'{engine}-run.json').read_text())
            self.assertEqual(record['build_report_sha256'],hashlib.sha256((build/'build-report.json').read_bytes()).hexdigest())
            self.assertEqual(record['program_sha256'],report['program_sha256'])
            self.assertEqual(set(record['raw_sha256']),{f'{engine}-{c}.bin' for c in CASES})
            for case in CASES:
                path=results/f'{engine}-{case}.bin';data=path.read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),record['raw_sha256'][path.name])
                value=decode(data,case) if isinstance(case,int) else negative(data,case)
                self.assertEqual(value,record['decoded'][str(case)])
        for directory in (build.parent,results):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                sha,n=line.split('  ',1)
                self.assertEqual(hashlib.sha256((directory/n).read_bytes()).hexdigest(),sha,n)

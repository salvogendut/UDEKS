# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
from window_cache_c_runtime import NAME,decode,negative,reference
from placement_audit import parse_map
from gen_capability_imports import map_exports


def synthetic(case=0):
    data=bytearray(8096);data[:8]=b'CRUN\x01\x02'+bytes((case,0))
    rows,calls,images=(132,547,66) if case==0 else (208,439,1)
    data[8:10]=rows.to_bytes(2,'little');data[10:12]=calls.to_bytes(2,'little')
    data[12:14]=b'\x01\x00';data[14]=images;data[22]=222;data[23]=15
    data[64:]=reference(case)
    return data


class WindowCacheCRuntimeTests(unittest.TestCase):
    def test_decoder_requires_all_runtime_guards_and_exact_work(self):
        good=synthetic();self.assertEqual(decode(good,0)['policy_calls'],547)
        self.assertEqual(decode(synthetic(1),1)['rows'],208)
        for offset in (4,5,6,7,8,10,14,15,16,17,18,19,20,21,23,26,63,64,8095):
            data=bytearray(good);data[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):decode(data,0)
        for offset,value in ((12,0),(22,0x3f),(22,0xf0)):
            data=bytearray(good);data[offset]=value
            with self.subTest(offset=offset,value=value),self.assertRaises(ValueError):decode(data,0)
        with self.assertRaises(ValueError):decode(good[:-1],0)
        with self.assertRaises(ValueError):decode(good,255)

    def test_interrupt_total_uses_upper_word_not_only_low_word(self):
        data=synthetic();data[12:14]=bytes(2);data[24:26]=b'\x01\x00'
        self.assertEqual(decode(data,0)['interrupts'],65536)
        data[12:14]=b'\xff\xff'
        self.assertEqual(decode(data,0)['interrupts'],131071)

    def test_negative_decoder_requires_exact_failure_and_full_oracle(self):
        for name,fields in (('irq-leak',(15,)),('zp-leak',(16,)),('shell-stack',(19,21))):
            data=synthetic()
            for i in fields:data[i]=1
            if name=='shell-stack':data[22]=0xf0
            self.assertEqual(negative(data,name)['detected_fields'],list(fields))
            with self.assertRaises(ValueError):decode(data,0)
            for offset in (7,8,10,14,20,23,26,64,8095):
                bad=bytearray(data);bad[offset]^=1
                with self.subTest(name=name,offset=offset),self.assertRaises(ValueError):negative(bad,name)
            for i in fields:
                bad=bytearray(data);bad[i]=0
                with self.assertRaises(ValueError):negative(bad,name)

    def test_measured_module_and_bindings_fit_candidates_not_claimed_production(self):
        directory=ROOT / 'bench/artifacts' / NAME;build=directory / 'build'
        report=json.loads((build / 'build-report.json').read_text())
        self.assertIn('standalone',report['qualification'])
        self.assertEqual(report['module_bytes'],213+118+1828+526)
        self.assertEqual(report['module_state_bytes'],28)
        self.assertEqual(report['cc65_record_bytes'],{'lease':13,'geometry':6,'row':9})
        self.assertEqual(report['c_gateway_bytes'],59)
        self.assertEqual(report['c_binding_object']['CODE'],83)
        self.assertEqual(report['row_binding_object']['CODE'],194)
        self.assertEqual(516-83-194,239)
        for name in ('c_binding_object','row_binding_object','policy_object'):
            self.assertEqual(report[name]['BSS'],0)
            self.assertEqual(report[name]['ZEROPAGE'],0)
        objects,segments=parse_map((build / 'module.map').read_text())
        layout={n:(s,e) for n,s,e in segments}
        self.assertEqual(layout['ZEROPAGE'],(6,31))
        self.assertEqual(layout['PRIVATESTATE'],(0x4cd0,0x4ceb))
        self.assertLess(layout['CODE'][1],0x4cd0)
        self.assertEqual(report['candidate_private_stack'],[0x4d00,0x4def])
        self.assertEqual(report['candidate_image'],[0x4e00,0x5bff])
        self.assertEqual(report['caller_stack_top'],0xeff0)
        self.assertEqual(report['protected_worker_shell_stack'],[0xe700,0xefff])
        symbols=map_exports((build / 'module.map').read_text())
        expected={'sp':6,'sreg':8,'regsave':10,'ptr1':14,'ptr2':16,'ptr3':18,
                  'ptr4':20,'tmp1':22,'tmp2':23,'tmp3':24,'tmp4':25,'regbank':26}
        self.assertEqual({n:symbols[n][0] for n in expected},expected)
        module=(build / 'module.bin').read_bytes()
        row=ROOT / 'bench/artifacts/2026-09-28-window-cache-overlay/build/core.bin'
        self.assertEqual(module[:213],row.read_bytes())
        envelope=module.ljust(0xb00,b'\x00')
        self.assertEqual((build / 'module-envelope.bin').read_bytes(),envelope)
        for case in (0,1):
            self.assertEqual((build / f'probe-{case}.prg').read_bytes().count(envelope),1)
            _,caller=parse_map((build / f'probe-{case}.map').read_text())
            self.assertEqual({n:(s,e) for n,s,e in caller}['ZEROPAGE'],(6,31))
        for name,sha in report['linked_sha256'].items():
            self.assertEqual(hashlib.sha256((build / name).read_bytes()).hexdigest(),sha,name)
        for name,sha in report['source_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)

    def test_fault_prgs_change_only_one_live_gateway_byte(self):
        directory=ROOT / 'bench/artifacts' / NAME;build=directory / 'build'
        report=json.loads((build / 'build-report.json').read_text())
        normal=(build / 'probe-0.prg').read_bytes();gate=(build / 'c-gateway.bin').read_bytes()
        self.assertEqual(normal.count(gate),1);start=normal.index(gate)
        for name,control in report['negative_controls'].items():
            bad=(build / f'probe-{name}.prg').read_bytes()
            self.assertEqual(len(normal),len(bad))
            changed=[i for i,(a,b) in enumerate(zip(normal,bad)) if a!=b]
            self.assertEqual(changed,[control['offset']])
            self.assertTrue(start<=changed[0]<start+len(gate))
            self.assertEqual((normal[changed[0]],bad[changed[0]]),(control['before'],control['after']))
        for name,sha in report['program_sha256'].items():
            self.assertEqual(hashlib.sha256((build / name).read_bytes()).hexdigest(),sha)

    def test_preserved_runs_are_bound_to_exact_programs_and_records(self):
        artifacts=ROOT / 'bench/artifacts' / NAME;results=ROOT / 'bench/results' / NAME
        report=json.loads((artifacts / 'build/build-report.json').read_text())
        decoded=json.loads((results / 'report.json').read_text())
        for engine in ('1986','vice'):
            run=json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(run['program_sha256'],report['program_sha256'])
            cases=(0,1,'irq-leak','zp-leak','shell-stack')
            self.assertEqual(set(run['raw_sha256']),{f'{engine}-{c}.bin' for c in cases})
            for c in cases:
                path=results / f'{engine}-{c}.bin';raw=path.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),run['raw_sha256'][path.name])
                value=decode(raw,c) if isinstance(c,int) else negative(raw,c)
                self.assertEqual(value,run['decoded'][str(c)])
                self.assertEqual(value,decoded[engine][str(c)])
        for directory in (artifacts,results):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,name=line.split('  ',1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)
            self.assertFalse(list(directory.rglob('*.vsf')))

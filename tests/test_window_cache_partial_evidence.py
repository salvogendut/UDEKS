# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import window_cache_partial as partial
from placement_audit import parse_map
from window_cache_controller_delivery import fixture


class PartialCacheEvidenceTests(unittest.TestCase):
    def test_preserved_emulator_runs_and_source_binding(self):
        archive=ROOT/'bench/artifacts'/partial.NAME
        results=ROOT/'bench/results'/partial.NAME
        report=json.loads((archive/'build/build-report.json').read_text())
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        for directory in (archive,results):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                value,name=line.split('  ',1)
                self.assertEqual(sha(directory/name),value,name)
        for key in ('linked_sha256','program_sha256'):
            for name,value in report[key].items():self.assertEqual(sha(archive/'build'/name),value)
        for name,value in report['source_sha256'].items():self.assertEqual(sha(archive/name),value)
        for engine in ('1986','vice'):
            run=json.loads((results/(engine+'-run.json')).read_text())
            self.assertEqual(run['build_report_sha256'],sha(archive/'build/build-report.json'))
            self.assertEqual(run['program_sha256'],report['program_sha256'])
            self.assertEqual(set(run['raw_sha256']),{f'{engine}-{c}.bin' for c in partial.compact.acceptance.CASES})
            for case in partial.compact.acceptance.CASES:
                path=results/f'{engine}-{case}.bin';data=path.read_bytes()
                self.assertEqual(sha(path),run['raw_sha256'][path.name])
                decoded=(partial.decode(data,case) if isinstance(case,int) else partial.negative(data,case))
                self.assertEqual(decoded,run['decoded'][str(case)])

    def test_fixed_memory_and_unchanged_assembly(self):
        archive=ROOT/'bench/artifacts'/partial.NAME
        provider=archive/'build/bench/window-cache-partial'
        module=(provider/'module.bin').read_bytes()
        gate=(provider/'gateway.bin').read_bytes()
        old=ROOT/'bench/artifacts/2026-09-28-window-cache-compact/build'
        self.assertEqual(module[:213],(old/'bench/window-cache-compact/module.bin').read_bytes()[:213])
        self.assertEqual(gate,(old/'gateway.bin').read_bytes())
        self.assertEqual(len(module),3971)
        self.assertEqual(fixture(module)[0x1010:0x1016],b'VCC2\x00\x01')
        segments={n:(s,e) for n,s,e in parse_map((provider/'module.map').read_text())[1]}
        self.assertEqual(segments['PRIVATESTATE'],(0x5220,0x5239))
        start,end=segments['DATA']
        self.assertEqual(end-start+1,3)
        self.assertLess(end,0x5210)
        self.assertEqual(module[start-0x4200:end-0x4200+1],bytes(3))
        report=json.loads((archive/'build/build-report.json').read_text())
        self.assertEqual(report['resident_bytes'],371)
        self.assertEqual(report['private_data_bytes'],3)
        for suffix,fault in report['negative_controls'].items():
            normal=(archive/'build/probe-0.prg').read_bytes()
            bad=(archive/f'build/probe-{suffix}.prg').read_bytes()
            self.assertEqual([i for i,(a,b) in enumerate(zip(normal,bad)) if a!=b],[fault['offset']])

    def test_decoder_cannot_normalize_away_failures(self):
        results=ROOT/'bench/results'/partial.NAME
        for case in (0,1):
            original=(results/f'1986-{case}.bin').read_bytes()
            for offset in (7,8,10,14,15,16,17,18,19,20,21,23,36,38,63,64,8064):
                bad=bytearray(original);bad[offset]^=1
                with self.assertRaises(ValueError,msg=f'case {case}, offset {offset}'):
                    partial.decode(bad,case)
        for name,offset in (('irq-leak',15),('zp-leak',16),('shell-stack',19)):
            bad=bytearray((results/f'1986-{name}.bin').read_bytes());bad[offset]=0
            with self.assertRaises(ValueError):partial.negative(bad,name)


if __name__=='__main__':unittest.main()

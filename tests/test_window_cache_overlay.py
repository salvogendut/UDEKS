# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_cache_overlay import NAME, decode, reference
from window_cache_bench import reference as old_reference, matrix_reference
from placement_audit import parse_map


class WindowCacheOverlayTests(unittest.TestCase):
    def test_pixel_oracle_matches_independent_existing_cases(self):
        self.assertEqual(reference(0), matrix_reference())
        self.assertEqual(reference(1), old_reference(10))

    def test_decoder_rejects_corruption_and_incomplete_records(self):
        for case in (0,1):
            data=bytearray(64)+bytearray(reference(case))
            data[:8]=b'OROW\x01\x02'+bytes((case,0))
            data[8:10]=(132 if case==0 else 320).to_bytes(2,'little')
            data[10]=66 if case==0 else 1
            data[12:14]=(1234).to_bytes(2,'little')
            data[16:18]=b'\x5a\xa5';data[19]=0xa5
            self.assertEqual(decode(data,case)['interrupts'],1234)
            for offset in (0,4,5,6,7,8,9,10,11,14,15,16,17,18,19,20,63,64,8064,8095):
                broken=data[:];broken[offset]^=1
                with self.subTest(case=case,offset=offset), self.assertRaises(ValueError):
                    decode(broken,case)
            with self.assertRaises(ValueError):decode(data[:-1],case)
            data[12:14]=bytes(2)
            with self.assertRaises(ValueError):decode(data,case)

    def test_actual_negative_control_changes_only_lease_sei(self):
        directory=ROOT / 'bench/artifacts' / NAME / 'build'
        report=json.loads((directory / 'build-report.json').read_text())
        original=(directory / 'probe-0.prg').read_bytes()
        negative=(directory / 'probe-irq-leak.prg').read_bytes()
        offset=report['negative_control']['offset']
        self.assertEqual(len(original),len(negative))
        self.assertEqual([i for i,(a,b) in enumerate(zip(original,negative)) if a!=b],[offset])
        self.assertEqual((original[offset],negative[offset]),(0x78,0xea))
        results=ROOT / 'bench/results' / NAME
        for engine in ('1986','vice'):
            data=(results / f'{engine}-irq-leak.bin').read_bytes()
            self.assertEqual(data[:8],b'OROW\x01\x02\x00\x00')
            self.assertEqual(data[14],1)
            with self.assertRaises(ValueError):decode(data,0)

    def test_footprint_includes_binding_image_but_not_diagnostic_uploader(self):
        directory=ROOT / 'bench/artifacts' / NAME / 'build'
        report=json.loads((directory / 'build-report.json').read_text())
        self.assertEqual(report['core_bytes'],213)
        self.assertEqual(report['gateway_bytes'],170)
        self.assertEqual(report['binding_object']['CODE'],194)
        self.assertTrue(all(report['binding_object'][name]==0 for name in ('BSS','DATA','RODATA','ZEROPAGE')))
        self.assertEqual(report['core_reservation'],[0x4200,0x43ff])
        self.assertEqual(report['cache_reservation'],[0x4400,0x5bff])
        self.assertLessEqual(len((directory / 'core.bin').read_bytes()),512)
        self.assertEqual(len((directory / 'gateway.bin').read_bytes()),170)
        self.assertEqual(0x5c00-0x4400,6144)
        self.assertLessEqual(28*160,6144)
        self.assertGreater(40*200,6144)
        self.assertEqual(report['row_stage'],[0xf7b0,0xf7d7])
        self.assertLess(report['row_stage'][1],0xf7f0)
        self.assertEqual(516-report['binding_object']['CODE'],322)
        objects,_=parse_map((directory / 'probe-0.map').read_text())
        self.assertEqual(objects['binding.o']['CODE'],194)
        image=(directory / 'probe-0.prg').read_bytes()
        self.assertEqual(image.count((directory / 'core.bin').read_bytes()),1)
        self.assertEqual(image.count((directory / 'gateway.bin').read_bytes()),2)

    def test_worker_core_has_no_kernel_runtime_dependency(self):
        directory=ROOT / 'bench/window-cache-overlay'
        core=(directory / 'core.s').read_text()
        gateway=(directory / 'gateway.s').read_text()
        binding=(directory / 'binding.s').read_text()
        self.assertNotIn('.import',core)
        self.assertNotIn('.importzp',gateway)
        self.assertIn('jsr READ',core)
        self.assertIn('jmp WRITE',core)
        self.assertIn('php\n        sei\n        cld',gateway)
        self.assertIn('sta KERNEL\n        plp\n        rts',gateway)
        self.assertIn('plp\n        jmp RUN',binding)
        instructions='\n'.join(line.split(';',1)[0] for line in
            (directory / 'layout.inc').read_text().lower().splitlines())
        self.assertNotIn('$f400',instructions)

    def test_preserved_build_and_run_hashes_and_full_pixels(self):
        artifacts=ROOT / 'bench/artifacts' / NAME
        results=ROOT / 'bench/results' / NAME
        report=json.loads((artifacts / 'build/build-report.json').read_text())
        for name,sha in report['source_sha256'].items():
            self.assertEqual(hashlib.sha256((artifacts / name).read_bytes()).hexdigest(),sha)
        for engine in ('1986','vice'):
            run=json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(run['program_sha256'],report['program_sha256'])
            self.assertEqual(set(run['raw_sha256']),{f'{engine}-{case}.bin' for case in (0,1,'irq-leak')})
            for name,sha in run['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((results / name).read_bytes()).hexdigest(),sha)
            for case in (0,1):
                self.assertEqual(decode((results / f'{engine}-{case}.bin').read_bytes(),case),
                    json.loads((results / 'report.json').read_text())['cases'][case][engine])
        for name,sha in report['program_sha256'].items():
            self.assertEqual(hashlib.sha256((artifacts / 'build' / name).read_bytes()).hexdigest(),sha)
        for directory in (artifacts,results):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,name=line.split('  ',1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)

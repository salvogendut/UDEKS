# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from test_window_cache_bench import HARNESS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_cache_bench import decode, decode_matrix, matrix_reference, validate_run_report
from window_cache_compare import compare
from window_cache_padding_fault import check_fault

MOCK_ROWS = r'''
static unsigned owned, begins;
void cache_transfer_begin(void) {assert(!owned);owned=1;++begins;}
void cache_transfer_fast(unsigned char mode) {
    assert(owned);
    cache_transfer(mode);
    if(mode==2) owned=0;
}
void cache_capture_row(void) {
    assert(owned);
    for(unsigned i=0;i<count;++i) {
        stage[i]=0;
        unsigned char mask=i+1==count?cache_row_last_mask:255;
        for(unsigned bit=0;bit<8;++bit) if(mask & (128>>bit)) {
            unsigned px=cache_row_shift+bit;
            unsigned offset=cache_row_offset+i*8+(px/8)*8;
            assert(offset<8000);
            if(shadow[offset] & (128>>(px%8))) stage[i]|=128>>bit;
        }
    }
}
void cache_paste_row(void) {
    assert(owned);
    for(unsigned i=0;i<count;++i) {
        unsigned char mask=i+1==count?cache_row_last_mask:255;
        for(unsigned bit=0;bit<8;++bit) if(mask & (128>>bit)) {
            unsigned px=cache_row_shift+bit;
            unsigned offset=cache_row_offset+i*8+(px/8)*8;
            assert(offset<8000);
            unsigned char m=128>>(px%8);
            if(stage[i] & (128>>bit)) shadow[offset]|=m;
            else shadow[offset]&=(unsigned char)~m;
            dirty[offset>>8]=1;
        }
    }
}
'''


class WindowCacheAssemblyTests(unittest.TestCase):
    def test_run_manifest_rejects_missing_matrix_and_stale_build_or_records(self):
        programs = {f'cache-{case}.prg': str(case) for case in list(range(11)) + ['matrix']}
        build = {'variant': 'asm', 'program_sha256': programs}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            raw = {}
            for case in list(range(11)) + ['matrix']:
                content = str(case).encode()
                name = f'1986-{case}.bin'
                (path / name).write_bytes(content)
                raw[name] = hashlib.sha256(content).hexdigest()
            run = {'variant': 'asm', 'program_sha256': programs.copy(), 'raw_sha256': raw.copy()}
            validate_run_report(run, build, path, '1986')
            del run['raw_sha256']['1986-matrix.bin']
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                validate_run_report(run, build, path, '1986')
            run['raw_sha256'] = raw.copy()
            run['program_sha256']['cache-matrix.prg'] = 'old'
            with self.assertRaisesRegex(ValueError, 'different build'):
                validate_run_report(run, build, path, '1986')
            run['program_sha256'] = programs.copy()
            run['variant'] = 'c'
            with self.assertRaisesRegex(ValueError, 'different build'):
                validate_run_report(run, build, path, '1986')
            run['variant'] = 'asm'
            run['raw_sha256']['1986-matrix.bin'] = 'wrong'
            with self.assertRaisesRegex(ValueError, 'changed'):
                validate_run_report(run, build, path, '1986')

    def test_real_c_wrapper_validation_and_nonreentrant_lease(self):
        source = (ROOT / 'bench/window-cache/cache-fast.c').read_text()
        for name, value in {'ADDRESS': 'address', 'COUNT': 'count'}.items():
            source, changed = re.subn(r'^#define ' + name + r' .*$',
                                      '#define ' + name + ' ' + value, source, flags=re.M)
            self.assertEqual(changed, 1)
        harness = HARNESS.replace('static unsigned index_at', MOCK_ROWS + '\nstatic unsigned index_at')
        harness = harness.replace('assert(!memcmp(stage,bank+0x4000,256));',
                                  'assert(!owned && begins);assert(!memcmp(stage,bank+0x4000,256));')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.c').write_text(harness.replace('SOURCE', source))
            subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-D__fastcall__=', '-I', str(ROOT / 'bench/window-cache'),
                            str(path / 'test.c'), '-o', str(path / 'test')], check=True, capture_output=True)
            subprocess.run([str(path / 'test')], check=True, capture_output=True)

    def test_row_matrix_decoder_requires_all_pixels_guards_and_count(self):
        block = bytearray(64) + bytearray(matrix_reference())
        block[:8] = b'WROW\x01\x02\x00\x00'
        block[8:14] = b'\x42\x00\x00\x00\x5a\xa5'
        self.assertEqual(decode_matrix(block)['checks'], 66)
        for offset in (0, 4, 5, 6, 7, 8, 9, 12, 13, 14, 63, 64, 8064):
            damaged = block[:]; damaged[offset] ^= 1
            with self.assertRaises(ValueError): decode_matrix(damaged)
        with self.assertRaises(ValueError): decode_matrix(block[:-1])

    def test_preserved_assembly_evidence_and_same_input_comparison(self):
        name = '2026-09-28-window-cache-asm'
        results = ROOT / 'bench/results' / name
        artifact = ROOT / 'bench/artifacts' / name
        actual = decode(results / 'raw')
        actual['matrix'] = {engine: decode_matrix((results / 'raw' / f'{engine}-matrix.bin').read_bytes())
                            for engine in ('1986', 'vice')}
        self.assertEqual(actual, json.loads((results / 'report.json').read_text()))
        comparison = compare(ROOT / 'bench/results/2026-09-28-window-cache-transfer', results)
        self.assertEqual(comparison, json.loads((results / 'comparison.json').read_text()))
        self.assertTrue(comparison['1986_same_inputs'])
        self.assertTrue(comparison['vice_same_flatpak'])
        for case in comparison['cases'][:8]:
            self.assertGreater(case['vice']['paste']['speedup'], 4)
        build = json.loads((artifact / 'build-report.json').read_text())
        self.assertEqual(build['variant'], 'asm')
        self.assertEqual(build['gateway'], {'size': 99, 'run': 0xF68A, 'end_inclusive': 0xF6EC})
        self.assertEqual(build['cache_object']['CODE'], 607)
        self.assertEqual(build['cache_object']['BSS'], 13)
        self.assertEqual(build['rows_object']['CODE'], 267)
        self.assertEqual(build['rows_object']['BSS'], 5)
        self.assertEqual(build['transfer_object']['CODE'], 131)
        self.assertEqual(len(build['program_sha256']), 12)
        for source, digest in build['sources_sha256'].items():
            self.assertEqual(hashlib.sha256((artifact / source).read_bytes()).hexdigest(), digest)
        for program, digest in build['program_sha256'].items():
            self.assertEqual(hashlib.sha256((artifact / program).read_bytes()).hexdigest(), digest)
        for engine in ('1986', 'vice'):
            run = json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(run['program_sha256'], build['program_sha256'])
            for record, digest in run['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((results / 'raw' / record).read_bytes()).hexdigest(), digest)
            negative = (results / 'raw' / f'{engine}-padding-negative.bin').read_bytes()
            fault = json.loads((results / f'{engine}-padding-negative.json').read_text())
            self.assertEqual(check_fault(negative), fault['record'])
            mutation = fault['mutation']
            reference = (artifact / 'cache-matrix.prg').read_bytes()
            bad = (artifact / 'cache-padding-negative.prg').read_bytes()
            self.assertEqual(hashlib.sha256(reference).hexdigest(), mutation['reference_sha256'])
            self.assertEqual(hashlib.sha256(bad).hexdigest(), mutation['negative_sha256'])
            offset = mutation['instruction_address'] - int.from_bytes(reference[:2], 'little') + 2
            rebuilt = bytearray(reference)
            self.assertEqual(reference[offset:offset+3].hex(), mutation['original'])
            rebuilt[offset:offset+3] = bytes.fromhex(mutation['replacement'])
            self.assertEqual(rebuilt, bad)
        for directory in (results, artifact):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                digest, filename = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((directory / filename).read_bytes()).hexdigest(), digest, filename)

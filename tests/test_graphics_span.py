# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from graphics_span_bench import replace_fill, matrix_operations, matrix_reference, decode_span, compare, validate_fault
from graphics_raster_bench_build import function


class GraphicsSpanTests(unittest.TestCase):
    def test_replacement_keeps_every_other_display_function(self):
        source = (ROOT / 'bench/artifacts/2026-09-28-graphics-span/sources/src/services/display/vic_graphics.c').read_text()
        candidate = replace_fill(source)
        old = function(source, 'udeks_vic_bitmap_fill').rstrip()
        new = (ROOT / 'bench/graphics-span/fill.c').read_text()
        self.assertEqual(candidate.replace(new, old), source)
        with self.assertRaises(ValueError): replace_fill('')

    def test_real_c_clipping_wrapper_with_mocked_span(self):
        # This executes the real C geometry/row wrapper, not ASM on the host.
        # Actual ASM qualification is separately recorded on both emulators.
        fragment = (ROOT / 'bench/graphics-span/fill.c').read_text()
        prefix = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static unsigned int bitmap_rows[200];
static unsigned char shadow[8000], expected[8000], dirty[32], expected_dirty[32];
static int clip_left, clip_top, clip_right, clip_bottom;
static unsigned calls;
'''
        harness = r'''
void udeks_span_fill_row(void) {
    ++calls;
    assert(udeks_span_count>=1 && udeks_span_count<=40);
    for (unsigned c=0;c<udeks_span_count;++c) {
        unsigned mask=c==0?udeks_span_first:255;
        if (c+1==udeks_span_count) mask &= udeks_span_last;
        unsigned off=udeks_span_offset+8*c;
        assert(off<8000 && mask);
        if (udeks_span_color==0) shadow[off]|=mask;
        else shadow[off]&=(unsigned char)~mask;
        dirty[off/256]=1;
    }
    udeks_span_offset+=8*(udeks_span_count-1);
}
static unsigned rng=1;
static unsigned random_value(void) {rng=rng*1664525u+1013904223u;return rng;}
int main(void) {
    for (unsigned y=0;y<200;++y) bitmap_rows[y]=(y/8)*320+y%8;
    for (unsigned trial=0;trial<2000;++trial) {
        for (unsigned i=0;i<8000;++i) expected[i]=shadow[i]=(i*13+trial*7);
        memset(dirty,0,32); memset(expected_dirty,0,32);
        clip_left=random_value()%321;clip_right=clip_left+random_value()%(321-clip_left);
        clip_top=random_value()%201;clip_bottom=clip_top+random_value()%(201-clip_top);
        int x=(int)(random_value()%600)-140,y=(int)(random_value()%400)-100;
        int w=(int)(random_value()%400)-30,h=(int)(random_value()%300)-30;
        unsigned char color=random_value()%256;
        unsigned before=calls;
        udeks_vic_bitmap_fill(x,y,w,h,color);
        if (w>0 && h>0) for (int yy=y;yy<y+h;++yy) for (int xx=x;xx<x+w;++xx) {
            if(xx<clip_left||xx>=clip_right||yy<clip_top||yy>=clip_bottom)continue;
            unsigned off=(yy/8)*320+(xx/8)*8+yy%8,mask=128>>(xx%8);
            if(color==0)expected[off]|=mask;else expected[off]&=(unsigned char)~mask;
            expected_dirty[off/256]=1;
        }
        assert(!memcmp(expected,shadow,8000));assert(!memcmp(expected_dirty,dirty,32));
        if(w<=0||h<=0||x>=clip_right||y>=clip_bottom||x+w<=clip_left||y+h<=clip_top)
            assert(before==calls);
    }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.c').write_text(prefix + fragment + harness)
            subprocess.run(['cc', '-std=c99', '-O0', '-Wall', '-Wextra', str(path / 'test.c'),
                            '-o', str(path / 'test')], check=True, capture_output=True)
            subprocess.run([str(path / 'test')], check=True, capture_output=True)

    def test_alignment_matrix_and_isolated_crossing(self):
        operations = matrix_operations()
        self.assertEqual(len(operations), 210)
        for color in range(2):
            selected = operations[color*64:(color+1)*64]
            self.assertEqual({(x%8,(x+w-1)%8) for x,y,w,h,c in selected},
                             {(a,b) for a in range(8) for b in range(8)})
            self.assertEqual({y%8 for x,y,w,h,c in selected}, set(range(8)))
        self.assertEqual(matrix_reference(5)[8000:], b'\x01\x01' + bytes(30))

    def test_matrix_decoder_rejects_each_result_component(self):
        for case in (4, 5):
            data = bytearray(64) + bytearray(matrix_reference(case))
            data[:8] = b'RAST\x01\x02' + bytes((1,case)); data[8:12]=(123).to_bytes(4,'little')
            data[12:15]=b'\x5a\xa5\xc3'
            self.assertEqual(decode_span(data,1,case),123)
            for off in (0,5,6,7,12,13,14,15,64,8064,8065):
                damaged = data[:]; damaged[off]^=1
                with self.subTest(case=case,off=off), self.assertRaises(ValueError):
                    decode_span(damaged,1,case)
            with self.assertRaises(ValueError): decode_span(data[:-1],1,case)
            data[8:12]=bytes(4)
            with self.assertRaises(ValueError): decode_span(data,1,case)

    def test_private_span_has_no_mmu_or_service_calls(self):
        text=(ROOT/'bench/graphics-span/span.s').read_text()
        self.assertNotRegex(text,r'\bjsr\b')
        self.assertNotRegex(text,r'\$(?:d50[0-9]|ff0[0-4])\b')
        self.assertIn('ldy _udeks_span_offset+1', text)
        self.assertNotIn('ldy ptr1+1', text)
        self.assertIn('cpx #$01',text)
        self.assertIn('and _udeks_span_last',text)

    def test_preserved_machine_and_link_qualification(self):
        artifacts=ROOT/'bench/artifacts/2026-09-28-graphics-span'
        results=ROOT/'bench/results/2026-09-28-graphics-span'
        report=json.loads((artifacts/'build/build-report.json').read_text())
        self.assertEqual(report['object_net_saving'],86)
        self.assertEqual(report['linked_net_saving'],86)
        self.assertEqual(report['span']['CODE'],102)
        self.assertEqual(report['linked_helpers']['c-reference'],report['linked_helpers']['asm-span'])
        for name in ('ZEROPAGE','SYSCALLS','TASKGATE','TASKREQUEST','LOWBSS','HIGHBSS'):
            self.assertEqual(report['experimental_link']['c-reference'][name],
                             report['experimental_link']['asm-span'][name])
        self.assertEqual(report['experimental_link']['c-reference']['VICSHADOW']['start'],0xA1E0)
        self.assertEqual(report['experimental_link']['asm-span']['VICSHADOW']['start'],0xA18A)
        self.assertEqual(compare(results),json.loads((results/'report.json').read_text()))
        for directory in (artifacts,results):
            for line in (directory/'SHA256SUMS').read_text().splitlines():
                sha,name=line.split('  ',1)
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),sha,name)
        expected={f'{label}-{case}.prg' for label in ('c-reference','asm-span') for case in (2,3,4,5)}
        self.assertEqual(set(report['program_sha256']),expected)
        for engine in ('1986','vice'):
            run=json.loads((results/f'{engine}-run.json').read_text())
            self.assertEqual(run['program_sha256'],report['program_sha256'])
            for name,sha in run['program_sha256'].items():
                self.assertEqual(hashlib.sha256((artifacts/'build'/name).read_bytes()).hexdigest(),sha)
            self.assertEqual(set(run['raw_sha256']),{f'{engine}-{label}-{case}.bin'
                for label in ('c-reference','asm-span') for case in (2,3,4,5)})
            for name,sha in run['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((results/name).read_bytes()).hexdigest(),sha)

    def test_preserved_dirty_negative_control(self):
        artifacts=ROOT/'bench/artifacts/2026-09-28-graphics-span/build'
        results=ROOT/'bench/results/2026-09-28-graphics-span'
        metadata=json.loads((artifacts/'negative-dirty.json').read_text())
        base=(artifacts/'asm-span-5.prg').read_bytes()
        fault=(artifacts/'negative-dirty.prg').read_bytes()
        offset=metadata['file_offset']
        self.assertEqual(base[offset:offset+3],bytes.fromhex(metadata['before']))
        self.assertEqual(fault[offset:offset+3],bytes.fromhex(metadata['after']))
        self.assertEqual(base[:offset]+base[offset+3:],fault[:offset]+fault[offset+3:])
        self.assertEqual(hashlib.sha256(base).hexdigest(),metadata['base_sha256'])
        self.assertEqual(hashlib.sha256(fault).hexdigest(),metadata['fault_sha256'])
        for engine in ('1986','vice'):
            data=(results/f'{engine}-negative-dirty.bin').read_bytes()
            validate_fault(data)
            with self.assertRaises(ValueError):decode_span(data,1,5)
            altered=bytearray(data);altered[64]^=1
            with self.assertRaises(ValueError):validate_fault(altered)
            manifest=json.loads((results/f'{engine}-fault.json').read_text())
            self.assertEqual(manifest,{'program_sha256':hashlib.sha256(fault).hexdigest(),
                                      'raw_sha256':hashlib.sha256(data).hexdigest()})

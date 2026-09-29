# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from graphics_shared_bench import reference, decode, compare, variant


class GraphicsSharedTests(unittest.TestCase):
    def test_real_shared_c_geometry_against_pixel_oracle(self):
        prefix = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "udeks/vic_graphics.h"
static unsigned char bitmap[8000], expected[8000], dirty[32], expected_dirty[32];
static unsigned int bitmap_rows[200];
static int clip_left, clip_top, clip_right, clip_bottom;
static unsigned int unsigned_magnitude(int v) { return v<0?(unsigned int)-v:(unsigned int)v; }
static void plot(unsigned char *bits, unsigned char *pages, int x,int y,unsigned char color) {
    if(x<clip_left||x>=clip_right||y<clip_top||y>=clip_bottom)return;
    unsigned off=(y/8)*320+(x/8)*8+y%8, mask=128>>(x%8);
    if(color==0)bits[off]|=mask;else bits[off]&=(unsigned char)~mask;
    pages[off/256]=1;
}
void udeks_vic_bitmap_pixel(int x,int y,unsigned char color) {plot(bitmap,dirty,x,y,color);}
'''
        span = (ROOT / 'bench/graphics-span/fill.c').read_text()
        line = (ROOT / 'bench/graphics-shared/line.c').read_text()
        rectangle = (ROOT / 'bench/graphics-shared/rectangle.c').read_text()
        harness = r'''
void udeks_span_fill_row(void) {
    for(unsigned i=0;i<udeks_span_count;++i) {
        unsigned mask=i?255:udeks_span_first;
        if(i+1==udeks_span_count)mask&=udeks_span_last;
        unsigned off=udeks_span_offset+8*i;
        assert(off<8000);
        if(udeks_span_color==0)bitmap[off]|=mask;else bitmap[off]&=(unsigned char)~mask;
        dirty[off/256]=1;
    }
}
static void ref_line(int x,int y,int xx,int yy,unsigned char color) {
    int dx=abs(xx-x),dy=-abs(yy-y),sx=x<xx?1:-1,sy=y<yy?1:-1,error=dx+dy;
    for(;;) {
        plot(expected,expected_dirty,x,y,color);if(x==xx&&y==yy)return;
        int twice=error*2;
        if(twice>=dy){error+=dy;x+=sx;}
        if(twice<=dx){error+=dx;y+=sy;}
    }
}
static unsigned rng=1;
static unsigned random_value(void){rng=rng*1664525u+1013904223u;return rng;}
int main(void) {
    for(unsigned y=0;y<200;++y)bitmap_rows[y]=(y/8)*320+y%8;
    for(unsigned trial=0;trial<1000;++trial) {
        for(unsigned i=0;i<8000;++i)bitmap[i]=expected[i]=(i*13+trial*7);
        memset(dirty,0,32);memset(expected_dirty,0,32);
        clip_left=random_value()%321;clip_right=clip_left+random_value()%(321-clip_left);
        clip_top=random_value()%201;clip_bottom=clip_top+random_value()%(201-clip_top);
        int x=(int)(random_value()%420)-50,y=(int)(random_value()%300)-50;
        int xx=(int)(random_value()%420)-50,yy=(int)(random_value()%300)-50;
        unsigned char color=random_value()%256;
        udeks_vic_bitmap_line(x,y,xx,yy,color);ref_line(x,y,xx,yy,color);
        assert(!memcmp(bitmap,expected,8000));assert(!memcmp(dirty,expected_dirty,32));
        int w=(int)(random_value()%400)-10,h=(int)(random_value()%250)-10;
        udeks_vic_bitmap_rectangle(x,y,w,h,color);
        if(w>0&&h>0) {
            for(int c=x;c<x+w;++c){plot(expected,expected_dirty,c,y,color);plot(expected,expected_dirty,c,y+h-1,color);}
            for(int r=y;r<y+h;++r){plot(expected,expected_dirty,x,r,color);plot(expected,expected_dirty,x+w-1,r,color);}
        }
        assert(!memcmp(bitmap,expected,8000));assert(!memcmp(dirty,expected_dirty,32));
    }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.c').write_text(prefix + span + line + rectangle + harness)
            subprocess.run(['cc', '-std=c99', '-O0', '-Wall', '-Wextra', '-I', str(ROOT / 'include'),
                str(path / 'test.c'), '-o', str(path / 'test')], check=True, capture_output=True)
            subprocess.run([str(path / 'test')], check=True, capture_output=True)

    def test_decoder_rejects_stack_guard_dirty_and_pixel_damage(self):
        for case in range(6):
            block = bytearray(64) + bytearray(reference(case))
            block[:8] = b'SHRD\x01\x02' + bytes((1, case))
            block[8:12] = (123).to_bytes(4, 'little'); block[12:15]=b'\x5a\xa5\xc3'
            self.assertEqual(decode(block,1,case),123)
            for offset in (0,5,6,7,12,13,14,15,63,64,8064,8095):
                broken=block[:];broken[offset]^=1
                with self.subTest(case=case,offset=offset), self.assertRaises(ValueError):
                    decode(broken,1,case)
            with self.assertRaises(ValueError):decode(block[:-1],1,case)
            block[8:12]=bytes(4)
            with self.assertRaises(ValueError):decode(block,1,case)

    def test_clear_uses_exact_extent_and_no_callbacks_or_banking(self):
        text = (ROOT / 'bench/graphics-shared/clear.s').read_text()
        self.assertIn('ldx #31', text)
        self.assertIn('cpy #64', text)
        self.assertIn('sta $e190,x', text)
        self.assertNotRegex(text, r'\bjsr\b|\$(?:d50[0-9]|ff0[0-4])\b')
        self.assertEqual(reference(4), bytes([255])*8000 + bytes([1])*32)
        self.assertEqual(reference(5), bytes(8000) + bytes([1])*32)

    def test_preserved_machine_and_whole_link_evidence(self):
        artifacts = ROOT / 'bench/artifacts/2026-09-28-graphics-shared'
        results = ROOT / 'bench/results/2026-09-28-graphics-shared'
        report = json.loads((artifacts / 'build/build-report.json').read_text())
        self.assertEqual(report['clear_asm']['CODE'], 52)
        self.assertEqual(report['combined']['net_saving'], 294)
        self.assertEqual(report['linked_net_saving'], 294)
        self.assertEqual(report['helpers']['reference'],report['helpers']['combined'])
        self.assertEqual(compare(results),json.loads((results / 'report.json').read_text()))
        expected={f'{label}-{case}.prg' for label in ('reference','combined') for case in range(6)}
        self.assertEqual(set(report['program_sha256']),expected)
        for engine in ('1986','vice'):
            manifest=json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(manifest['program_sha256'],report['program_sha256'])
            self.assertEqual(set(manifest['raw_sha256']),
                {f'{engine}-{label}-{case}.bin' for label in ('reference','combined') for case in range(6)})
            for name,sha in manifest['program_sha256'].items():
                self.assertEqual(hashlib.sha256((artifacts / 'build' / name).read_bytes()).hexdigest(),sha)
            for name,sha in manifest['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((results / name).read_bytes()).hexdigest(),sha)
        for directory in (artifacts,results):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,name=line.split('  ',1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)

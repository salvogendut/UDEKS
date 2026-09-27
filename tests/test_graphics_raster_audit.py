# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import re
import subprocess
import tempfile
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from graphics_raster_audit import static_scratch_variant, static_arguments_variant, segment_sizes


class GraphicsRasterAuditTests(unittest.TestCase):
    def test_preserved_report_matches_the_audited_source(self):
        report = json.loads((ROOT / 'bench/results/2026-09-27-graphics-raster-audit/report.json').read_text())
        source = (ROOT / 'src/services/display/vic_graphics.c').read_bytes()
        self.assertEqual(report['source_sha256'], hashlib.sha256(source).hexdigest())
        self.assertEqual(report['code_saved'], report['baseline']['CODE'] - report['static-scratch']['CODE'])
        self.assertEqual(report['bss_added'], report['static-scratch']['BSS'] - report['baseline']['BSS'])
        self.assertEqual(report['net_object_bytes_saved'], 49)
        self.assertEqual(report['arguments_net_object_bytes_saved'], -45)
        self.assertIn('compile-only', report['qualification'])

    def test_only_two_local_declaration_blocks_change(self):
        original = (ROOT / 'src/services/display/vic_graphics.c').read_text()
        variant = static_scratch_variant(original)
        self.assertEqual(variant.replace('    static ', '    '), original)
        self.assertEqual(variant.count('    static '), 18)

    def test_layout_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'declaration block'):
            static_scratch_variant('void udeks_vic_bitmap_line(void) {}')

    def test_object_segment_parser(self):
        dump = '\n'.join(f'Name: "{name}"\nFlags: 0\nSize: {size}'
                         for name, size in [('CODE', 4347), ('BSS', 0), ('VICSHADOW', 8000)])
        self.assertEqual(segment_sizes(dump)['CODE'], 4347)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            segment_sizes(dump + '\nName: "CODE"\nFlags: 0\nSize: 1')
        with self.assertRaisesRegex(ValueError, 'missing'):
            segment_sizes('')

    def test_baseline_and_static_variant_against_pixel_reference(self):
        original = (ROOT / 'src/services/display/vic_graphics.c').read_text()
        for source in (original, static_scratch_variant(original), static_arguments_variant(original)):
            # Keep the real clear/pixel/line/fill implementation. Discard unused
            # hardware-facing sections at link time, and replace only MMIO state.
            source = source.split('void udeks_vic_bitmap_set_clip(', 1)[0]
            source = re.sub(r'#define STATUS_BYTE\(offset\).*?\n\n',
                            '#define STATUS_BYTE(offset) test_status[offset]\n\n',
                            source, count=1, flags=re.S)
            for name in ('bitmap_rows', 'dirty_pages', 'clip_left', 'clip_top',
                         'clip_right', 'clip_bottom'):
                source = re.sub(r'^#define ' + name + r' .*$',
                                '#define ' + name + ' test_' + name,
                                source, flags=re.M)
            prefix = '''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static unsigned char test_status[32], test_dirty_pages[32];
static unsigned int test_bitmap_rows[200];
static int test_clip_left, test_clip_top, test_clip_right, test_clip_bottom;
'''
            harness = r'''
static unsigned char expected[8000], expected_dirty[32];
static void pixel(int x,int y,unsigned char color) {
    if (x<test_clip_left || x>=test_clip_right || y<test_clip_top || y>=test_clip_bottom) return;
    unsigned offset=(y&248)*40+(x&~7)+(y&7);
    unsigned char mask=128>>(x&7);
    if (color==UDEKS_VIC_COLOR_BLACK) expected[offset]|=mask;
    else expected[offset]&=(unsigned char)~mask;
    expected_dirty[offset>>8]=1;
}
static void reference_line(int x,int y,int xx,int yy,unsigned char color) {
    int dx=abs(xx-x),dy=-abs(yy-y),sx=x<xx?1:-1,sy=y<yy?1:-1,error=dx+dy;
    for (;;) {
        pixel(x,y,color); if (x==xx && y==yy) break;
        int twice=error*2;
        if (twice>=dy) {error+=dy;x+=sx;}
        if (twice<=dx) {error+=dx;y+=sy;}
    }
}
static unsigned rng=1;
static unsigned random_value(void) {rng=rng*1664525u+1013904223u;return rng;}
int main(void) {
    for (unsigned y=0;y<200;++y) test_bitmap_rows[y]=(y&248)*40+(y&7);
    for (unsigned trial=0;trial<500;++trial) {
        for (unsigned i=0;i<8000;++i) expected[i]=udeks_vic_bitmap_shadow[i]=(i+trial)*13;
        memset(test_dirty_pages,0,32);memset(expected_dirty,0,32);
        test_clip_left=random_value()%160;test_clip_right=test_clip_left+random_value()%161;
        test_clip_top=random_value()%100;test_clip_bottom=test_clip_top+random_value()%101;
        int x=(int)(random_value()%420)-50,y=(int)(random_value()%300)-50;
        int xx=(int)(random_value()%420)-50,yy=(int)(random_value()%300)-50;
        unsigned char color=trial&1;
        udeks_vic_bitmap_line(x,y,xx,yy,color);reference_line(x,y,xx,yy,color);
        assert(!memcmp(expected,udeks_vic_bitmap_shadow,8000));
        assert(!memcmp(expected_dirty,test_dirty_pages,32));
        int w=(int)(random_value()%120)-10,h=(int)(random_value()%120)-10;
        udeks_vic_bitmap_fill(x,y,w,h,color);
        for (int r=y;r<y+h;++r) for (int c=x;c<x+w;++c) pixel(c,r,color);
        assert(!memcmp(expected,udeks_vic_bitmap_shadow,8000));
        assert(!memcmp(expected_dirty,test_dirty_pages,32));
    }
}
'''
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                (path / 'test.c').write_text(prefix + source + harness)
                subprocess.run(['cc', '-std=c99', '-O0', '-ffunction-sections',
                                '-fdata-sections', '-Wl,--gc-sections', '-I',
                                str(ROOT / 'include'), str(path / 'test.c'),
                                '-o', str(path / 'test')], check=True, capture_output=True)
                subprocess.run([str(path / 'test')], check=True, capture_output=True)

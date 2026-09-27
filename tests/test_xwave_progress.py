# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute the actual application C against host mocks, not a rendering model."""
import re
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include <assert.h>
#include <stdint.h>
static unsigned char test_status[32], test_samples[25];
SOURCE
static udeks_window_paint_fn paint;
static udeks_window_close_fn close_callback;
static unsigned leases, lines, commits;
static unsigned allowed = 1, fallback;
static unsigned int gx = 144, gw = 168;
static unsigned char gy = 88, gh = 104;
static unsigned char actual[64000], expected[64000];
static void line(unsigned char *bitmap, int x, int y, int xx, int yy) {
    int dx = abs(xx-x), sx = x<xx ? 1 : -1;
    int dy = -abs(yy-y), sy = y<yy ? 1 : -1, err = dx+dy;
    for (;;) {
        assert(x>=0 && x<320 && y>=0 && y<200);
        bitmap[y*320+x] = 1;
        if (x==xx && y==yy) break;
        int e = 2*err;
        if (e>=dy) {err+=dy; x+=sx;}
        if (e<=dx) {err+=dx; y+=sy;}
    }
}
unsigned char udeks_z80_submit(unsigned char op, unsigned int row,
        unsigned int count, unsigned int width, unsigned int *result) {
    assert(op==UDEKS_MB_OP_SURFACE_ROWS && count==1 && width==25);
    ++leases;
    if (fallback) return UDEKS_Z80_NOT_READY;
    for (unsigned c=0;c<25;++c) test_samples[c]=local_surface_height(row,c);
    *result=row+1; return UDEKS_Z80_OK;
}
unsigned char udeks_vic_graphics_is_active(void) {return 1;}
void udeks_vic_bitmap_line(int x,int y,int xx,int yy,unsigned char color) {
    assert(color==UDEKS_VIC_COLOR_BLACK); ++lines; line(actual,x,y,xx,yy);
}
unsigned char udeks_window_get_geometry(unsigned char h, unsigned int *x,
        unsigned char *y, unsigned int *w, unsigned char *hh) {
    assert(h==1); *x=gx; *y=gy; *w=gw; *hh=gh; return UDEKS_WINDOW_OK;
}
unsigned char udeks_window_create(unsigned char o,unsigned char s,unsigned char f,
        unsigned int x,unsigned char y,unsigned int w,unsigned char h,
        const unsigned char *title,udeks_window_paint_fn p,udeks_window_close_fn c) {
    (void)o;(void)s;(void)f;(void)x;(void)y;(void)w;(void)h;(void)title;
    paint=p; close_callback=c; paint(1); return 1;
}
unsigned char udeks_window_destroy(unsigned char h) {close_callback(h);return 0;}
unsigned char udeks_window_begin_paint(unsigned char h) {(void)h;return allowed?0:1;}
void udeks_window_end_paint(void) {++commits;}
unsigned char udeks_window_is_dragging(unsigned char h) {(void)h;return !allowed;}
unsigned char udeks_window_is_focused(unsigned char h) {(void)h;return allowed;}
static void check_bitmap(void) {
    memset(expected,0,sizeof expected);
    for (int r=0;r<21;++r) for (int c=0;c<25;++c) {
        int lx=(c+20-r)*4, ly=28+c+r;
        int px=gx+3+lx*(gw-6)/176;
        int py=gy+UDEKS_WINDOW_TITLE_HEIGHT+1+
            (ly-local_surface_height(r,c))*(gh-UDEKS_WINDOW_TITLE_HEIGHT-5)/75;
        if (c && !(r&1)) line(expected,
            gx+3+(lx-4)*(gw-6)/176,
            gy+UDEKS_WINDOW_TITLE_HEIGHT+1+
            (ly-1-local_surface_height(r,c-1))*(gh-UDEKS_WINDOW_TITLE_HEIGHT-5)/75,
            px,py);
        if (r && !(c&1)) line(expected,
            gx+3+(lx+4)*(gw-6)/176,
            gy+UDEKS_WINDOW_TITLE_HEIGHT+1+
            (ly-1-local_surface_height(r-1,c))*(gh-UDEKS_WINDOW_TITLE_HEIGHT-5)/75,
            px,py);
    }
    assert(!memcmp(actual,expected,sizeof actual));
}
int main(void) {
    for (fallback=0;fallback<2;++fallback) {
        memset(actual,0,sizeof actual); leases=lines=commits=0;
        assert(udeks_xwave_initialize()==0 && udeks_xwave_start()==0);
        assert(!leases && !lines); /* create must not draw the entire grid */
        for (unsigned i=0;draw_row<21 && i<200;++i) {
            unsigned l=leases, n=lines;
            udeks_xwave_poll();
            assert(leases-l<=1 && lines-n<=8);
            if (i==10) {
                unsigned saved_offset=draw_offset;
                allowed=0; udeks_xwave_poll(); allowed=1;
                assert(draw_offset==saved_offset);
                memset(actual,0,sizeof actual); paint(1);
                assert(leases==l || leases==l+1);
                assert(draw_offset==saved_offset);
            }
        }
        assert(draw_row==21 && leases==21 && commits==147);
        check_bitmap();
        unsigned l=leases;
        gx=12; gy=12; gw=220; gh=160;
        memset(actual,0,sizeof actual); paint(1); check_bitmap();
        assert(leases==l); /* resize must not recompute mathematical samples */
        udeks_xwave_stop(); assert(!udeks_xwave_is_running());
        udeks_xwave_poll(); assert(leases==l);
        gx=144; gy=88; gw=168; gh=104;
    }
    udeks_xwave_initialize(); udeks_xwave_start(); udeks_xwave_poll();
    udeks_xwave_stop(); unsigned l=leases;
    udeks_xwave_poll(); assert(leases==l && draw_row<21);
    udeks_xwave_start(); while(draw_row<21) udeks_xwave_poll();
    assert(udeks_xwave_is_running());
}
'''


class XwaveProgressTests(unittest.TestCase):
    def test_qualified_disks_logs_and_native_records(self):
        for kind in ('artifacts', 'results'):
            directory = ROOT / 'bench' / kind / '2026-09-27-xwave-responsive'
            for entry in (directory / 'SHA256SUMS').read_text().splitlines():
                digest, filename = entry.split('  ', 1)
                self.assertEqual(hashlib.sha256((directory / filename).read_bytes()).hexdigest(),
                                 digest, filename)
        directory = ROOT / 'bench/results/2026-09-27-xwave-responsive'
        for disk in ('d71', 'd64'):
            log = (directory / f'1986-{disk}.log').read_text()
            self.assertIn('wave: cancel during row=0 column=4 leases=1', log)
            self.assertIn('wave: cancelled in 222 frames, row=0', log)
            self.assertIn('complete rows=21 leases=21; cached drag without recomputation', log)
            diagnostic = (directory / f'raw/1986-{disk}-diagnostics.bin').read_bytes()
            wave = diagnostic[0x150:0x170]
            self.assertEqual(wave[:8], b'XWAV\x04\x03\x00\x07')
            self.assertEqual(wave[12:16], b'\x15\x00\x00\x00')
            self.assertEqual(wave[26:28], b'\x15\x00')
            self.assertEqual(diagnostic[11], 0)  # UTSK canary failures

    def test_real_c_bounded_progress_cache_and_cancellation(self):
        source = (ROOT / "src/apps/xwave.c").read_text()
        source = re.sub(r'#define STATUS_BYTE\(offset\).*?\n#define WINDOW_X',
                        '#define STATUS_BYTE(offset) test_status[offset]\n'
                        '#define SAMPLE_BYTE(offset) test_samples[offset]\n\n'
                        '#define WINDOW_X', source, flags=re.S)
        source = source.replace('UDEKS_XWAVE_STATUS_BASE + offset',
                                '(uintptr_t)(test_status + offset)')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.c').write_text('#include <stdlib.h>\n#include <string.h>\n' +
                                        HARNESS.replace('SOURCE', source))
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'include'), str(path / 'test.c'),
                            '-o', str(path / 'test')], check=True, capture_output=True)
            subprocess.run([str(path / 'test')], check=True, capture_output=True)

# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import re
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
from window_completion_probe import NAME,inspect,window_base
from placement_audit import parse_map

class WindowCompletionTests(unittest.TestCase):
    def test_real_manager_rejects_ineligible_and_withdraws_before_mutation(self):
        harness=r'''
#include <assert.h>
static unsigned char test_status[32];
SOURCE
static unsigned clips,fills,commits;
void udeks_vic_bitmap_set_clip(int x,int y,int w,int h)
{(void)x;(void)y;(void)w;(void)h;++clips;}
void udeks_vic_bitmap_reset_clip(void) {}
void udeks_vic_bitmap_commit(void) {++commits;}
void udeks_vic_bitmap_fill(int x,int y,int w,int h,unsigned char c)
{(void)x;(void)y;(void)w;(void)h;(void)c;++fills;
 assert(!(windows[0].flags&IMAGE_COMPLETE));}
void udeks_vic_bitmap_pixel(int x,int y,unsigned char c) {(void)x;(void)y;(void)c;}
void udeks_vic_bitmap_line(int x,int y,int xx,int yy,unsigned char c)
{(void)x;(void)y;(void)xx;(void)yy;(void)c;}
void udeks_vic_bitmap_rectangle(int x,int y,int w,int h,unsigned char c)
{(void)x;(void)y;(void)w;(void)h;(void)c;}
static void paint(unsigned char handle) {(void)handle;}
int main(void) {
    struct udeks_window *w=&windows[0];
    w->active=1;w->surface=UDEKS_WINDOW_SURFACE_BITMAP;
    w->flags=UDEKS_WINDOW_FLAG_VISIBLE;w->z=1;w->x=7;w->y=7;w->width=168;w->height=104;
    active_count=1;focused_handle=0; /* Topmost, not keyboard focus, is required. */
    assert(udeks_window_image_complete(1)==0 && (w->flags&IMAGE_COMPLETE));
    assert(udeks_window_image_complete(1)==0); /* Idempotent */
    for(unsigned i=0;i<6;++i) {
        unsigned char flags=w->flags;
        if(i==0)w->active=0;if(i==1)active_count=2;if(i==2)dragging_handle=2;
        if(i==3)w->flags=0;if(i==4)w->surface=2;
        assert(udeks_window_image_complete(i==5?5:1)==1);
        if(i!=3)assert(w->flags==flags);else assert(w->flags==0);
        w->active=1;active_count=1;dragging_handle=0;w->surface=1;w->flags=flags;
    }
    assert(clips==0 && fills==0 && commits==0); /* Notification draws nothing */
    assert(udeks_window_begin_paint(1)==0 && !(w->flags&IMAGE_COMPLETE));
    udeks_window_end_paint();assert(!(w->flags&IMAGE_COMPLETE));
    assert(udeks_window_image_complete(1)==0);
    damage_left=200;damage_right=250;damage_top=150;damage_bottom=190;
    assert(paint_window_damage(1)==0 && (w->flags&IMAGE_COMPLETE));
    damage_set(w);assert(paint_window_damage(1)==1);
    assert(!(w->flags&IMAGE_COMPLETE) && fills==1);
    w->active=0;assert(udeks_window_image_complete(1)==1);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            manager=(ROOT / 'src/services/window/window_manager.c').read_text()
            manager=re.sub(r'#define STATUS_BYTE\(offset\).*?\n\n',
                '#define STATUS_BYTE(offset) test_status[offset]\n\n',manager,count=1,flags=re.S)
            work=Path(directory);path=work / 'test.c';path.write_text(harness.replace('SOURCE',manager))
            compiled=subprocess.run(['cc','-std=c99','-D__fastcall__=','-Wno-unknown-pragmas',
                '-ffunction-sections','-fdata-sections','-I',str(ROOT),'-I',str(ROOT / 'include'),
                str(path),'-Wl,--gc-sections','-o',str(work / 'test')],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            subprocess.run([str(work / 'test')],check=True,capture_output=True)

    def test_completion_vector_preserves_table_and_old_kernel_fallback(self):
        gateway=(ROOT / 'src/8502/app_gateway.s').read_text()
        client=(ROOT / 'user/lib/window_completion.s').read_text()
        wave=(ROOT / 'src/apps/xwave.c').read_text()
        manager=(ROOT / 'src/services/window/window_manager.c').read_text()
        self.assertIn('.byte $00, $04',gateway)
        self.assertIn('.byte $35, $03',gateway)
        self.assertIn('.addr _udeks_window_image_complete\n        .addr _udeks_window_take_click\n        .res 4, $00',gateway)
        self.assertEqual(sum(line.strip().startswith('jmp ') for line in gateway.splitlines()),53)
        extension=client.split('_udeks_window_image_complete:\n',1)[1]
        self.assertLess(extension.index('lda $cf54'),extension.index('jmp ($cf58)'))
        self.assertIn('cmp #$03\n        bcc no_completion',extension)
        self.assertIn('lda #$01\n        ldx #$00\n        rts',extension)
        self.assertIn('if (draw_row == SURFACE_ROWS) {',wave)
        self.assertIn('udeks_window_image_complete(window_handle);',wave)
        self.assertIn('(flags & 0x0Fu)',manager)
        repaint=manager.split('static unsigned char paint_window_damage(unsigned char handle)\n{')[1]
        repaint=repaint.split('static void compose_damage',1)[0]
        self.assertLess(repaint.index('window->flags &= (unsigned char)~IMAGE_COMPLETE;'),
                        repaint.index('udeks_vic_bitmap_fill('))

    def test_byte_sized_projection_is_exact_for_all_surface_vertices(self):
        for row in range(21):
            for column in range(25):
                value=(column+20-row)*4
                self.assertEqual(value,value&255)

    def test_qualified_normal_disks_records_and_frozen_placement(self):
        artifacts=ROOT / 'bench/artifacts' / NAME;results=ROOT / 'bench/results' / NAME
        for directory in (artifacts,results):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha,name=line.split('  ',1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)
        report=json.loads((artifacts / 'build-report.json').read_text())
        self.assertEqual((report['resident_charge'],report['remaining_padding'],report['bootfs_free']),
                         (158,358,0))
        self.assertEqual(window_base((artifacts / 'build/8502/udeks-8502.map').read_text()),
                         report['window_base'])
        original=ROOT / 'bench/artifacts/2026-09-28-graphics-shared-integration/build/8502/udeks-8502.map'
        self.assertEqual(parse_map(original.read_text())[1],
                         parse_map((artifacts / 'build/8502/udeks-8502.map').read_text())[1])
        for fmt,sha in report['disk_sha256'].items():
            self.assertEqual(hashlib.sha256((artifacts / f'udeks.{fmt}').read_bytes()).hexdigest(),sha)
        for engine in ('1986','vice'):
            run=json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(run['build_report_sha256'],hashlib.sha256(
                (artifacts / 'build-report.json').read_bytes()).hexdigest())
            for name,sha in run['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((results / name).read_bytes()).hexdigest(),sha)
            for fmt in ('d71','d64'):
                w=(results / f'{engine}-{fmt}-windows.bin').read_bytes()
                g=(results / f'{engine}-{fmt}-gateway.bin').read_bytes()
                self.assertEqual(inspect(w,g,report['completion_entry']),run['decoded'][fmt])
                for offset in (0,4,5,6,7,8,10,16,172):
                    bad=bytearray(g);bad[offset]^=1
                    with self.subTest(offset=offset),self.assertRaises(ValueError):
                        inspect(w,bad,report['completion_entry'])
            if engine=='1986':
                for fmt in ('d71','d64'):
                    log=(results / f'1986-{fmt}.log').read_text()
                    self.assertEqual(log.count('completion: explicit topmost image certified'),2)
                    self.assertIn('PASS: native boot, stable idle, typing/backspace/history, 1351 drag',log)

    def test_preserved_shadow_and_install_gate_is_the_same_normal_disk(self):
        directory=ROOT / 'bench/results' / (NAME+'-layout')
        for line in (directory / 'SHA256SUMS').read_text().splitlines():
            sha,name=line.split('  ',1)
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),sha,name)
        report=json.loads((directory / 'report.json').read_text())
        build=json.loads((ROOT / 'bench/artifacts' / NAME / 'build-report.json').read_text())
        self.assertEqual(report['disk_sha256'],build['disk_sha256']['d71'])
        self.assertEqual((report['shadow_clear_bytes'],report['tail_preimage_bytes'],report['remaining_padding']),
                         (8000,50,358))
        self.assertFalse(any((directory / 'shadow-boot.bin').read_bytes()[:8000]))
        self.assertEqual((directory / 'shadow-drawn.bin').read_bytes(),(directory / 'vic-bitmap.bin').read_bytes())
        self.assertEqual(hashlib.sha256((directory / 'vic-bitmap.bin').read_bytes()).hexdigest(),
                         report['bitmap_sha256'])

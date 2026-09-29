# SPDX-License-Identifier: GPL-3.0-or-later
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
import window_repaint_raster as raster


class RasterBudgetTests(unittest.TestCase):
    def test_guards_reject_omitted_functions_and_hidden_allocations(self):
        fixture={'compact':{'segments':{'HIGHBSS':76}},
                 'replacement':{'segments':{'HIGHBSS':88},'functions':{n:{} for n in
                    ('_chrome_pixel','_chrome_span','_draw_chrome_row','_lane_raster_step','_draw_chrome')}},
                 'receipt':{'segments':{}},'binding':{'segments':{}}}
        raster.verify_components(fixture)
        for n in fixture['replacement']['functions']:
            bad=copy.deepcopy(fixture);del bad['replacement']['functions'][n]
            with self.assertRaises(ValueError):raster.verify_components(bad)
        for obj,seg in (('replacement','HIGHBSS'),('replacement','BSS'),('receipt','DATA'),
                        ('receipt','HIGHBSS'),('binding','ZEROPAGE')):
            bad=copy.deepcopy(fixture);bad[obj]['segments'][seg]=bad[obj]['segments'].get(seg,0)+1
            with self.assertRaises(ValueError):raster.verify_components(bad)

    def test_source_keeps_rejection_and_transient_pointer_rules(self):
        chrome=(ROOT / 'bench/window-repaint-raster/chrome.inc').read_text()
        scratch=chrome.split('#pragma bss-name(push, "HIGHBSS")',1)[1].split('#pragma bss-name(pop)',1)[0]
        self.assertNotIn('*',scratch)
        self.assertIn('const unsigned char *text;',chrome)
        self.assertNotIn('static const unsigned char *text',chrome)
        backend=(ROOT / 'bench/window-repaint-raster/raster.inc').read_text()
        self.assertLess(backend.index('repaint_receipt_validate(&work->ticket)'),backend.index('udeks_vic_bitmap_set_clip('))
        self.assertIn('work->ticket.cursor >= UDEKS_VIC_BITMAP_PAGES',backend)
        self.assertIn('work->clip.bottom - work->clip.top > UDEKS_REPAINT_CLEAR_ROWS',backend)
        self.assertIn('work->ticket.cursor >= work->clip.bottom - work->clip.top',backend)
        self.assertIn('udeks_vic_bitmap_reset_clip();\n    return repaint_receipt_ack',backend)
        probe=(ROOT / 'bench/window-repaint-raster/probe.inc').read_text()
        self.assertIn('work=packet.work;',probe)
        self.assertIn('runtime_irq_stop();runtime_check_memory();',probe)

    def test_decoder_requires_exact_pixels_coverage_and_unmodified_workspace(self):
        data=bytearray(8096);data[:9]=b'RAST\x01\x02\0\0\x08'
        data[12]=1;data[23]=211;data[24]=15
        for i in range(8):data[32+i*2:34+i*2]=raster.checksum(raster.reference(i)).to_bytes(2,'little')
        data[64:8064]=raster.reference(7)
        self.assertEqual(raster.decode(data)['scenes'],8)
        for off in (7,8,9,12,16,17,18,19,20,21,22,24,25,32,48,64,8063,8064,8095):
            bad=bytearray(data);bad[off]^=1
            with self.subTest(offset=off),self.assertRaises(ValueError):raster.decode(bad)
        bad=bytearray(data);bad[23]=0x3F
        with self.assertRaises(ValueError):raster.decode(bad)

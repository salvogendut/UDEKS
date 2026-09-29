# SPDX-License-Identifier: GPL-3.0-or-later
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
import window_repaint_scenes as scenes
import window_repaint_raster as raster


class SceneBudgetTests(unittest.TestCase):
    def test_complete_charges_layout_and_stack_fail_closed(self):
        sizes={'_chrome_pixel':100,'_chrome_span':100,'_draw_chrome_row':775,
               '_lane_raster_step':755,'_repaint_frontend_allowed':48,
               '_repaint_frontend_control':98,'_repaint_frontend_poll':212}
        report={'object':{'segments':{'CODE':8491,'HIGHBSS':88},
                         'functions':{n:{'size':s} for n,s in sizes.items()}},
                'links':{n:{'code_growth':1012,'library_delta':72} for n in ('normal','panic')},
                'budget':{'charged':2371,'shortfall':258,'poll_saving':228},
                'module':{'segments':{'ZEROPAGE':[6,31],'ENTRY':[0xD100,0xD102],
                                     'CODE':[0xD103,0xDF87],'HIGHBSS':[0xDFE0,0xDFF1]},
                          'bytes':3720,'code_spare':88,'helper_bytes':512,'local_view_bytes':36,
                          'objects':{n:{'segments':{'CODE':s}} for n,s in (('lane',2641),('dispatch',564))}},
                'layout':{'expected':list(scenes.LAYOUT),'negative_prefix':[255],'negative_packet':[255]}}
        scenes.verify_budget(report)
        edits=[('object','segments','HIGHBSS',89),('object','segments','DATA',1),
               ('object','segments','ZEROPAGE',1),('budget','charged',2370),
               ('budget','shortfall',257),('budget','poll_saving',229),
               ('module','helper_bytes',511),('module','code_spare',89),
               ('module','local_view_bytes',0),('links','panic','code_growth',1011),
               ('links','panic','library_delta',71),('layout','expected',[0]),
               ('layout','negative_prefix',list(scenes.LAYOUT)),('layout','negative_packet',list(scenes.LAYOUT))]
        for edit in edits:
            bad=copy.deepcopy(report);node=bad
            for key in edit[:-2]:node=node[key]
            node[edit[-2]]=edit[-1]
            with self.subTest(edit=edit),self.assertRaises(ValueError):scenes.verify_budget(bad)
        for n in sizes:
            bad=copy.deepcopy(report);del bad['object']['functions'][n]
            with self.assertRaises(ValueError):scenes.verify_budget(bad)
        bad=copy.deepcopy(report);del bad['links']['panic']
        with self.assertRaises(ValueError):scenes.verify_budget(bad)

    def test_record_requires_new_protocol_coverage_and_exact_pixels(self):
        data=bytearray(8096);data[:10]=b'RAST\x02\x02\0\0\x08\x04'
        data[12]=1;data[23]=169;data[24]=15
        for i in range(8):data[32+i*2:34+i*2]=raster.checksum(raster.reference(i)).to_bytes(2,'little')
        data[64:8064]=raster.reference(7)
        # The wrapper may temporarily replace raster.decode during a run.
        old=raster.decode
        try:
            raster.decode=scenes.decode
            self.assertEqual(scenes.decode(data)['protocol_rejections'],4)
        finally:raster.decode=old
        for off in (4,5,7,8,9,12,16,17,18,19,20,21,22,24,25,32,48,64,8063,8064,8095):
            bad=bytearray(data);bad[off]^=1
            with self.subTest(offset=off),self.assertRaises(ValueError):scenes.decode(bad)
        bad=bytearray(data);bad[23]=63
        with self.assertRaises(ValueError):scenes.decode(bad)

    def test_only_value_prefix_is_copied_and_work_is_local(self):
        poll=(ROOT / 'bench/window-repaint-scenes/poll.inc').read_text()
        self.assertIn('memcpy(scene,window,8)',poll)
        self.assertIn('remaining=4;',poll)
        self.assertLess(poll.index('*output=packet.work;'),poll.index('return lane_raster_step(output);'))
        for forbidden in ('->paint(', 'window->title', '#pragma bss-name', 'while (', 'cache_step('):
            self.assertNotIn(forbidden,poll)
        decoder=(ROOT / 'bench/window-repaint-scenes/dispatch.c').read_text()
        self.assertIn('struct udeks_repaint_window views[4];',decoder)
        self.assertNotIn('static struct udeks_repaint_window',decoder)
        self.assertIn('scene->x>320u-scene->width',decoder)
        self.assertIn('scene->y>200u-scene->height',decoder)
        self.assertNotIn('UDEKS_REPAINT_RETAINED',decoder)

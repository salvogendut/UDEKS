# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the target C parser/viewer with a fake graphics/file veneer."""
import ctypes as c
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from png_to_cbm import build, pack_bits


class Viewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='udeks-xview-')
        binary=Path(cls.temp.name)/'viewer.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-DUDEKS_NATIVE_CONSOLE_HOST_TEST','-D__fastcall__=','-Iuser/include','-Iinclude',
            'user/bin/xview.c','tests/fixtures/xview.c','-o',str(binary)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(binary))
        cls.lib.udeks_program_main.argtypes=[c.c_uint8,c.POINTER(c.c_char_p)]
        cls.lib.udeks_program_main.restype=c.c_uint8
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self): self.lib.viewer_reset()
    def value(self,name,wide=False): return (c.c_uint if wide else c.c_uint8).in_dll(self.lib,'viewer_'+name)
    def load(self,data):
        self.value('size',True).value=len(data)
        (c.c_uint8*8012).in_dll(self.lib,'viewer_data')[:len(data)]=data
    def run_viewer(self,*args):
        return self.lib.udeks_program_main(len(args),(c.c_char_p*(len(args)+1))(*args,None))
    def text(self): return bytes((c.c_uint8*256).in_dll(self.lib,'viewer_text')).split(b'\0')[0]
    def render(self,w,h):
        pixels=[[0]*w for _ in range(h)]
        raw=bytes((c.c_uint8*1280).in_dll(self.lib,'viewer_retained'))
        for i in range(self.value('retained_count').value):
            op,x,y,*rows=raw[i*8:i*8+8]
            self.assertEqual(op,3)
            for ry,row in enumerate(rows):
                for rx in range(8):
                    if row&(128>>rx):
                        xx,yy=x-4+rx,y-14+ry
                        self.assertTrue(0<=xx<w and 0<=yy<h)
                        pixels[yy][xx]=1
        return pixels

    def test_exact_pixels_odd_sizes_partial_bands_short_reads_and_no_reread(self):
        rng=random.Random(3)
        for w,h in ((1,1),(9,7),(24,21),(64,64),(80,80),(128,50),(240,5)):
            self.setUp()
            rows=[[rng.randrange(2) for _ in range(w)] for _ in range(h)]
            data=build(pack_bits(rows),w,h); self.load(data)
            self.value('short_read').value=7
            self.assertEqual(self.run_viewer(b'xview',b'/test.cbm'),0,self.text())
            self.assertEqual(self.render(w,h),rows)
            self.assertEqual(self.value('offset',True).value,len(data))
            self.assertEqual(self.value('closes').value,1)
            self.assertEqual(self.value('creates').value,1)
            self.assertEqual(self.value('presents').value,1)
            self.assertEqual(self.value('events').value,3)
            self.assertEqual(self.value('window_closes').value,0)
            self.assertEqual(self.value('protocol_failure').value,0)
            self.assertGreater(self.value('sleeps',True).value,2)

    def test_blank_tiles_are_elided_without_losing_sparse_large_images(self):
        rows=[[0]*240 for _ in range(175)]
        for x,y in ((0,0),(239,174),(120,80)): rows[y][x]=1
        self.load(build(pack_bits(rows),240,175))
        self.assertEqual(self.run_viewer(b'xview',b'/sparse.cbm'),0)
        self.assertEqual(self.value('retained_count').value,3)
        self.assertEqual(self.render(240,175),rows)

    def test_tile_budget_is_checked_before_opening_window(self):
        self.load(build(b'\xff'*816,128,51))
        self.assertEqual(self.run_viewer(b'xview',b'/dense.cbm'),1)
        self.assertEqual(self.text(),b'xview: Picture exceeds viewer limits\n')
        self.assertEqual(self.value('creates').value,0)
        self.assertEqual(self.value('closes').value,1)

    def test_bad_files_never_open_or_paint_a_window(self):
        valid=build(b'\x80\0'*7,9,7)
        malformed=[b'',valid[:-1],valid+b'X',b'X'+valid[1:],valid[:4]+b'\2'+valid[5:],
                   valid[:5]+b'\0\0'+valid[7:], valid[:9]+b'\1\0'+valid[11:],
                   valid[:-1]+b'\1']
        for data in malformed:
            self.setUp(); self.load(data)
            self.assertEqual(self.run_viewer(b'xview',b'/bad.cbm'),1)
            self.assertEqual(self.text(),b'xview: Invalid CBM picture\n')
            self.assertEqual(self.value('creates').value,0)
            self.assertEqual(self.value('closes').value,1)

    def test_oversized_format_valid_file_fails_instead_of_cropping(self):
        for w,h in ((248,1),(1,176),(320,200)):
            self.setUp(); self.load(build(bytes(((w+7)//8)*h),w,h))
            self.assertEqual(self.run_viewer(b'xview',b'/big.cbm'),1)
            self.assertEqual(self.text(),b'xview: Picture exceeds viewer limits\n')
            self.assertEqual(self.value('creates').value,0)

    def test_usage_missing_read_sleep_close_failures_cleanup(self):
        self.assertEqual(self.run_viewer(b'xview'),2)
        self.assertEqual(self.text(),b'xview FILE.CBM\n')
        self.assertEqual(self.value('opens').value,0)
        self.setUp(); self.value('open_error').value=2
        self.assertEqual(self.run_viewer(b'xview',b'/missing'),1)
        self.assertIn(b'No such file',self.text())
        self.assertEqual(self.value('closes').value,0)
        for name in ('fail_at','sleep_error','close_error'):
            self.setUp(); self.load(build(b'\xff',8,1))
            self.value(name,name=='fail_at').value=5
            self.assertEqual(self.run_viewer(b'xview',b'/fail.cbm'),1)
            self.assertEqual(self.value('closes').value,1)
            self.assertEqual(self.value('creates').value,0)
            self.assertEqual(self.text(),b'xview: I/O error\n')

    def test_busy_present_retries_same_image_without_reading_disk(self):
        self.load(build(b'\xa0',8,1)); self.value('busy').value=2
        self.assertEqual(self.run_viewer(b'xview',b'/ok.cbm'),0)
        self.assertEqual(self.value('presents').value,3)
        self.assertEqual(self.value('reads',True).value,3)
        self.assertEqual(self.value('closes').value,1)
        self.assertEqual(self.render(8,1),[[1,0,1,0,0,0,0,0]])

    def test_shared_display_pool_failure_closes_window_and_reports(self):
        self.load(build(b'\xff',8,1)); self.value('present_error').value=12
        self.assertEqual(self.run_viewer(b'xview',b'/ok.cbm'),1)
        self.assertEqual(self.text(),b'xview: Not enough display memory\n')
        self.assertEqual(self.value('window_closes').value,1)

    def test_titles_follow_each_private_argument_and_are_padded(self):
        for path,title in ((b'/clockwork.cbm',b'clockwor'),(b'/alex.cbm',b'alex\0\0\0\0')):
            self.setUp(); self.load(build(b'\xff',8,1))
            self.assertEqual(self.run_viewer(b'xview',path),0)
            self.assertEqual(bytes((c.c_uint8*24).in_dll(self.lib,'viewer_geometry'))[7:15],title)

    def test_invalid_path_never_opens_and_unexpected_descriptor_is_not_closed(self):
        for path in (b'',b'/' + b'x'*23):
            self.setUp()
            self.assertEqual(self.run_viewer(b'xview',path),1)
            self.assertEqual(self.value('opens').value,0)
        self.setUp(); self.value('fd').value=7
        self.assertEqual(self.run_viewer(b'xview',b'/bad'),1)
        self.assertEqual(self.value('closes').value,0)
        self.setUp(); self.value('fd').value=3
        self.assertEqual(self.run_viewer(b'xview',b'/'),1)
        self.assertEqual(self.text(),b'xview: Is a directory\n')
        self.assertEqual(self.value('closes').value,1)

    def test_oversized_read_reply_and_high_header_bytes_fail_closed(self):
        self.load(build(b'\xff',8,1)); self.value('oversized_reply').value=1
        self.assertEqual(self.run_viewer(b'xview',b'/bad'),1)
        self.assertEqual(self.value('creates').value,0)
        for at in (6,8,10):
            self.setUp(); data=bytearray(build(b'\xff',8,1)); data[at]=255; self.load(data)
            self.assertEqual(self.run_viewer(b'xview',b'/bad'),1)
            self.assertEqual(self.text(),b'xview: Invalid CBM picture\n')

    def test_decode_failure_is_not_hidden_by_close_error(self):
        self.load(b'bad'); self.value('close_error').value=5
        self.assertEqual(self.run_viewer(b'xview',b'/bad'),1)
        self.assertEqual(self.text(),b'xview: Invalid CBM picture\n')

    def test_every_demo_decodes_and_pairs_fit_the_shared_display_pool(self):
        sizes=[]
        for name in ('ALEX','CLOCKWORK','ALEX2'):
            from png_to_cbm import parse
            self.setUp(); data=(ROOT/'PICS'/(name+'.CBM')).read_bytes(); self.load(data)
            w,h,rows=parse(data)
            self.assertEqual(self.run_viewer(b'xview',('/'+name+'.cbm').encode()),0)
            self.assertEqual(self.render(w,h),rows)
            sizes.append(self.value('retained_count').value*8)
        self.assertLessEqual(sum(sorted(sizes)[-2:]),2304)

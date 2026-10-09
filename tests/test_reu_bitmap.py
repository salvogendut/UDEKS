# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual public bitmap adapter with physical DMA mocked, not its allocator."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_reu_store import State

ROOT=Path(__file__).resolve().parents[1]
U8=C.c_ubyte


class ReuBitmapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        so=Path(cls.tmp.name)/'bitmap.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',
            '-Wno-unknown-pragmas','-shared','-fPIC','-D__fastcall__=',
            '-DUDEKS_BITMAP_REU','-Iinclude','tests/fixtures/reu_bitmap.c',
            'src/services/window/reu_bitmap.c','src/services/memory/reu_store.c',
            '-o',str(so)],cwd=ROOT,check=True)
        cls.lib=C.CDLL(str(so))
        cls.lib.bitmap_request.argtypes=[U8,C.POINTER(U8)]
        cls.lib.bitmap_request.restype=U8
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.lib.bitmap_reset()
        self.state=State.in_dll(self.lib,'udeks_reu_store')
        C.memset(C.addressof(self.state),0,C.sizeof(self.state))
        self.handles=(C.c_uint16*4).in_dll(self.lib,'udeks_bitmap_handles');self.handles[:]=[0]*4
        self.lengths=(C.c_uint*4).in_dll(self.lib,'udeks_retained_lengths')
        self.pool=(U8*2304).in_dll(self.lib,'graphics_pool')
        self.ram=(U8*32770).in_dll(self.lib,'mock_ram');self.ram[:]=bytes([165])*len(self.ram)
        for n in ('calls','fail'):C.c_uint.in_dll(self.lib,'mock_'+n).value=0
        U8.in_dll(self.lib,'mock_partial').value=0
        self.lib.udeks_reu_store_init(8)
    def snapshot(self):return bytes(self.state),bytes(self.pool),tuple(self.lengths),bytes(self.handles),bytes(self.ram)
    def request(self,index,payload,expected=0):
        before=self.snapshot()
        error=self.lib.bitmap_request(index,(U8*24)(*payload))
        self.assertEqual(error,expected)
        if error not in (0,5):self.assertEqual(before,self.snapshot())
    def upload(self,index,width=160,height=100):
        stride=(width+7)//8
        data=bytearray((i*37+index+1)&255 for i in range(stride*height))
        if width%8:
            for at in range(stride-1,len(data),stride):data[at]&=255<<(8-width%8)
        self.request(index,[8,1,width,0,height,4,0,14])
        for at in range(0,len(data),19):
            part=data[at:at+19];self.request(index,[9,1,at&255,at>>8,len(part),*part])
        self.request(index,[10,1])
        return data
    def test_four_large_objects_compaction_retirement_and_reuse(self):
        data=[self.upload(i,240,175) for i in range(4)]
        self.assertEqual(tuple(self.lengths),(0x4008,)*4)
        for i in range(4):self.assertEqual(bytes(self.ram[1+i*8192:1+i*8192+5250]),data[i])
        old=self.handles[1];self.lib.bitmap_discard(1)
        self.assertEqual(self.handles[1],0);self.assertEqual(self.state.objects[1].state,0)
        self.upload(1);self.assertGreater(self.handles[1],old)
        for i in (0,3,2,1):self.lib.bitmap_discard(i)
        self.assertFalse(any(self.lengths));self.assertFalse(any(o.state for o in self.state.objects))
        self.assertEqual((self.ram[0],self.ram[-1]),(165,165))
    def test_pending_invisible_invalid_requests_atomic_abort_cleans(self):
        self.request(2,[8,1,9,0,3,0,0,0])
        self.request(2,[9,1,0,0,2,255,1],22) # nonzero row padding
        self.request(2,[9,1,1,0,1,0],22)
        self.request(2,[10,1],22)
        self.request(2,[9,1,0,0,6,255,128,255,128,255,128])
        self.lib.udeks_retained_bitmap_paint(2)
        self.assertFalse(any((U8*64000).in_dll(self.lib,'bitmap_canvas')))
        self.request(2,[11,1]);self.assertFalse(any(self.lengths));self.assertFalse(self.handles[2])
    def test_ram_exhaustion_rejects_before_reu_allocation(self):
        self.lengths[0]=2304
        self.request(1,[8,1,160,0,100,0,0,0],12)
        self.assertEqual(self.state.serial,0)
    def test_stock_fallback_and_coexistence(self):
        self.lib.udeks_reu_store_init(0)
        pixels=self.upload(2)
        self.assertEqual(self.lengths[2],0x4000+2008)
        self.assertEqual(bytes(self.pool[8:2008]),pixels)
        self.assertFalse(any(self.handles))
        self.request(1,[8,1,128,0,80,0,0,0],12)
        self.assertEqual(C.c_uint.in_dll(self.lib,'mock_calls').value,0)
    def test_legacy_replacement_releases_only_on_success(self):
        self.upload(0)
        record=(U8*38).in_dll(self.lib,'graphics_request')
        record[14:38]=bytes(24)
        before=self.snapshot()
        self.assertEqual(self.lib.udeks_retained_present(0),22)
        self.assertEqual(before,self.snapshot())
        record[17]=0x23 # legal source, zero commands = clear
        self.assertEqual(self.lib.udeks_retained_present(0),0)
        self.assertFalse(self.handles[0]);self.assertFalse(self.state.objects[0].state)
        self.upload(0)
    def test_render_fetches_rows_after_compaction_clipping_and_failure(self):
        pixels=self.upload(3,9,7);self.upload(0,8,1)
        canvas=(U8*64000).in_dll(self.lib,'bitmap_canvas')
        C.c_uint.in_dll(self.lib,'bitmap_clip_left').value=7
        C.c_uint.in_dll(self.lib,'bitmap_clip_bottom').value=19
        self.lib.udeks_retained_bitmap_paint(3)
        expected=bytearray(64000)
        for y in range(5):
            for x in range(3,9):expected[(14+y)*320+4+x]=bool(pixels[y*2+x//8]&(128>>(x%8)))
        self.assertEqual(bytes(canvas),expected)
        canvas[:]=bytes(64000)
        C.c_uint.in_dll(self.lib,'mock_fail').value=C.c_uint.in_dll(self.lib,'mock_calls').value+1
        U8.in_dll(self.lib,'mock_partial').value=1
        self.lib.udeks_retained_bitmap_paint(3)
        self.assertFalse(any(canvas));self.assertEqual(self.state.device,2)
        self.lib.bitmap_discard(3);self.lib.bitmap_discard(0)
        self.assertFalse(any(o.state for o in self.state.objects))

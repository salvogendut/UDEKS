# SPDX-License-Identifier: GPL-3.0-or-later
"""Unlinked packed-store core: real C, shared pool, adversarial transactions."""
import ctypes as c
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class BitmapStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='udeks-bitmap-store-')
        target=Path(cls.temp.name)/'store.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-Iinclude','src/services/window/bitmap_store.c','tests/fixtures/bitmap_store.c',
            '-o',str(target)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(target))
        cls.lib.bitmap_request.argtypes=[c.c_ubyte,c.POINTER(c.c_ubyte)]
        cls.lib.bitmap_request.restype=c.c_ubyte
        cls.lib.bitmap_view.argtypes=[c.c_ubyte]
        cls.lib.bitmap_view.restype=c.c_void_p
        cls.lib.bitmap_discard.argtypes=[c.c_ubyte]
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self):
        self.lib.bitmap_reset()
        self.data=(c.c_ubyte*2306).in_dll(self.lib,'bitmap_guarded')
        self.lengths=(c.c_uint*4).in_dll(self.lib,'bitmap_lengths')
    def snapshot(self): return bytes(self.data),tuple(self.lengths)
    def request(self,index,payload,error=0):
        p=(c.c_ubyte*24)(*payload)
        before=self.snapshot()
        self.assertEqual(self.lib.bitmap_request(index,p),error)
        self.assertEqual(bytes(p),bytes(payload)+bytes(24-len(payload)))
        self.assertEqual((self.data[0],self.data[-1]),(165,165))
        if error: self.assertEqual(self.snapshot(),before)
    def begin(self,index,w,h,x=4,y=14,error=0):
        self.request(index,[8,1,w&255,w>>8,h,x&255,x>>8,y],error)
    def write(self,index,offset,data,error=0):
        self.request(index,[9,1,offset&255,offset>>8,len(data),*data],error)
    def upload(self,index,data,chunk=19):
        for at in range(0,len(data),chunk): self.write(index,at,data[at:at+chunk])
    def view(self,index):
        p=self.lib.bitmap_view(index)
        return c.string_at(p,self.lengths[index]&8191) if p else None

    def test_dense_bigger_pictures_are_exact_and_not_visible_until_commit(self):
        rng=random.Random(55)
        for w,h in ((128,80),(160,100),(240,75),(9,7)):
            self.setUp(); stride=(w+7)//8
            pixels=bytearray(rng.randrange(256) for _ in range(stride*h))
            if w&7:
                for row in range(h): pixels[(row+1)*stride-1]&=255<<(8-(w&7))
            self.begin(0,w,h)
            self.assertIsNone(self.view(0))
            self.upload(0,pixels)
            self.assertIsNone(self.view(0))
            self.request(0,[10,1])
            view=self.view(0)
            self.assertEqual(view[:6],bytes((4,0,14,w,h,stride)))
            self.assertEqual(int.from_bytes(view[6:8],'little'),len(pixels))
            self.assertEqual(view[8:],pixels)
            self.assertEqual(self.lengths[0],0x4000+8+len(pixels))

    def test_bad_dimensions_geometry_and_reserved_fields_are_atomic(self):
        for w,h in ((0,1),(1,0),(241,1),(256,1),(320,1),(1,176)):
            self.begin(0,w,h,error=22)
        for x,y in ((313,0),(0,200),(65535,0)):
            self.begin(0,8,1,x,y,error=22)
        self.request(0,[8,1,8,0,1,0,0,0,1],22)
        self.begin(0,240,175,x=0,y=0,error=12)
        self.begin(0,8,1,x=312,y=199)

    def test_index_and_unsupported_operation_are_rejected_without_mutation(self):
        for i in (4,7,255):
            self.begin(i,8,1,error=22)
            self.assertFalse(self.lib.bitmap_view(i))
            before=self.snapshot(); self.lib.bitmap_discard(i)
            self.assertEqual(self.snapshot(),before)
        self.request(0,[99,1],22)
        self.begin(0,8,1)
        self.request(0,[99,1],22)

    def test_begun_or_committed_image_cannot_be_silently_replaced(self):
        self.begin(0,8,1)
        self.begin(0,8,1,error=16)
        self.upload(0,b'\xff'); self.request(0,[10,1])
        self.begin(0,16,2,error=16)
        self.request(0,[10,1],22)
        self.request(0,[11,1],22)
        self.write(0,0,b'\0',22)

    def test_partial_out_of_order_overrun_and_zero_writes_are_atomic(self):
        self.begin(0,8,20)
        self.request(0,[10,1],22)
        self.write(0,0,b'',22)
        self.write(0,1,b'A',22)
        self.write(0,65535,b'A',22)
        self.request(0,[9,1,0,0,20],22)
        self.write(0,0,b'A'*19)
        self.request(0,[10,1],22)
        self.write(0,0,b'B',22)
        self.write(0,19,b'BC',22)
        self.write(0,19,b'B')
        self.request(0,[10,1,1],22)
        self.request(0,[10,1])
        self.assertEqual(self.view(0)[8:],b'A'*19+b'B')

    def test_padding_error_at_end_of_chunk_does_not_write_its_prefix(self):
        self.begin(0,9,5)
        self.write(0,0,bytes((255,128,255,1)),22)
        self.write(0,0,bytes((255,128,255)))
        self.write(0,3,bytes((1,255)),22)
        self.upload_tail(0,3,bytes((128,255,128,255,128,255,128)))
        self.request(0,[10,1])

    def upload_tail(self,index,at,data):
        for byte in data:
            self.write(index,at,bytes((byte,))); at+=1

    def test_reserved_write_tail_is_rejected(self):
        self.begin(0,8,1)
        self.request(0,[9,1,0,0,1,255,1],22)

    def test_abort_and_owner_retirement_release_pending_or_committed_bytes(self):
        self.begin(0,160,100); self.write(0,0,b'A'*19)
        self.request(0,[11,1,1],22)
        self.request(0,[11,1]); self.assertEqual(self.lengths[0],0)
        self.begin(0,8,1); self.lib.bitmap_discard(0)
        self.assertEqual(self.lengths[0],0)
        self.begin(0,8,1); self.upload(0,b'\xff'); self.request(0,[10,1])
        self.lib.bitmap_discard(0); self.assertEqual(self.lengths[0],0)
        self.lib.bitmap_discard(0); self.assertEqual(self.lengths[0],0)

    def test_peer_insert_remove_during_upload_preserves_geometry_cursor_and_pixels(self):
        self.begin(3,80,40); self.write(3,0,b'B'*19)
        self.begin(0,64,40); self.upload(0,b'A'*320); self.request(0,[10,1])
        self.upload_tail(3,19,b'B'*381)
        self.lib.bitmap_discard(0)
        self.request(3,[10,1]); self.assertEqual(self.view(3)[8:],b'B'*400)
        self.begin(1,8,1); self.upload(1,b'C'); self.request(1,[10,1])
        self.assertEqual(self.view(3)[8:],b'B'*400)
        self.lib.bitmap_discard(3); self.assertEqual(self.view(1)[8:],b'C')

    def test_existing_command_and_path_images_share_pool_without_corruption(self):
        self.lengths[0]=344; self.lengths[3]=0x8000|1128
        original=bytes((n*37)&255 for n in range(1472))
        self.data[1:1473]=original
        self.begin(1,160,100,error=12)
        self.begin(1,88,63); self.upload(1,b'\x55'*693); self.request(1,[10,1])
        self.assertEqual(bytes(self.data[1:345]),original[:344])
        self.assertEqual(bytes(self.data[1046:2174]),original[344:])
        self.assertIsNone(self.view(0)); self.assertIsNone(self.view(3))
        self.begin(2,128,80,error=12)
        self.lib.bitmap_discard(1)
        self.assertEqual(bytes(self.data[1:1473]),original)
        self.assertEqual(tuple(self.lengths),(344,0,0,0x8000|1128))

    def test_exact_pool_fill_and_one_byte_short(self):
        # 160x100 + 8 header = 2008, leaving exactly 296 bytes.
        self.lengths[3]=297
        self.begin(0,160,100,error=12)
        self.lengths[3]=296
        self.begin(0,160,100); self.upload(0,b'\xff'*2000); self.request(0,[10,1])
        self.assertEqual(sum(n&8191 for n in self.lengths),2304)
        self.assertEqual(self.view(0)[8:],b'\xff'*2000)
        self.begin(1,8,1,error=12)

    def test_four_independent_commits_survive_compaction_and_reuse(self):
        for i in (3,1,2,0):
            self.begin(i,8,1,x=i*40,y=i*10)
            self.upload(i,bytes((128>>i,))); self.request(i,[10,1])
        self.lib.bitmap_discard(1)
        self.begin(1,16,3); self.upload(1,b'\xaa'*6); self.request(1,[10,1])
        for i in (0,2,3):
            v=self.view(i)
            self.assertEqual(v[:6],bytes((i*40,0,i*10,8,1,1)))
            self.assertEqual(v[8:],bytes((128>>i,)))

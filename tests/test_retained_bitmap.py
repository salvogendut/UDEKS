# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare the service-bound handler to the independent portable C contract."""
import ctypes as c
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class RetainedBitmap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='udeks-retained-bitmap-')
        cls.libs=[]
        sources=[['src/services/window/bitmap_store.c','tests/fixtures/bitmap_store.c'],
                 ['tests/fixtures/retained_bitmap.c']]
        for i,files in enumerate(sources):
            target=Path(cls.temp.name)/(str(i)+'.so')
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',
                '-Wno-unknown-pragmas','-shared','-fPIC','-D__fastcall__=',
                '-Iinclude',*files,'-o',str(target)],cwd=ROOT,check=True)
            lib=c.CDLL(str(target))
            lib.bitmap_request.argtypes=[c.c_ubyte,c.POINTER(c.c_ubyte)]
            lib.bitmap_request.restype=c.c_ubyte
            lib.bitmap_discard.argtypes=[c.c_ubyte]
            cls.libs.append(lib)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        for lib in self.libs: lib.bitmap_reset()
        self.guarded=(c.c_ubyte*2306).in_dll(self.libs[0],'bitmap_guarded')
        self.pool=(c.c_ubyte*2304).in_dll(self.libs[1],'graphics_pool')
        self.lengths=[(c.c_uint*4).in_dll(lib,name) for lib,name in zip(self.libs,
            ('bitmap_lengths','udeks_retained_lengths'))]
        self.record=(c.c_ubyte*38).in_dll(self.libs[1],'graphics_request')

    def equivalent(self):
        self.assertEqual(bytes(self.guarded[1:-1]),bytes(self.pool))
        self.assertEqual(tuple(self.lengths[0]),tuple(self.lengths[1]))
        self.assertEqual((self.guarded[0],self.guarded[-1]),(165,165))

    def request(self,index,payload,expected=None):
        p=(c.c_ubyte*24)(*payload)
        before=bytes(self.pool),tuple(self.lengths[1])
        errors=[lib.bitmap_request(index,p) for lib in self.libs]
        self.assertEqual(errors[0],errors[1])
        if expected is not None: self.assertEqual(errors[0],expected)
        self.equivalent()
        self.assertEqual(bytes(self.record[14:]),bytes(p))
        if errors[0]: self.assertEqual((bytes(self.pool),tuple(self.lengths[1])),before)
        return errors[0]

    def discard(self,index):
        for lib in self.libs: lib.bitmap_discard(index)
        self.equivalent()

    def test_all_sizes_ordered_chunks_and_atomic_errors(self):
        for width,height in ((1,175),(9,65),(128,80),(160,100),(240,75)):
            self.setUp();stride=(width+7)//8
            pixels=bytearray((i*73)&255 for i in range(stride*height))
            if width&7:
                for i in range(stride-1,len(pixels),stride):pixels[i]&=255<<(8-(width&7))
            self.request(3,[8,1,width,0,height,0,0,0],0)
            self.request(3,[8,1,width,0,height,0,0,0],16)
            self.request(3,[10,1],22)
            self.request(3,[9,1,255,255,1,255],22)
            for at in range(0,len(pixels),19):
                data=pixels[at:at+19]
                self.request(3,[9,1,at&255,at>>8,len(data),*data],0)
            self.request(3,[10,1,1],22)
            self.request(3,[10,1],0)
            self.assertEqual(bytes(self.pool[8:8+len(pixels)]),pixels)
            self.request(3,[11,1],22)
            self.discard(3)

    def test_compaction_mixes_all_legacy_and_pending_flags(self):
        # Real allocator preserves the bytes belonging to commands and paths.
        for records in self.lengths: records[:]=(344,0x8000|1128,0,0)
        for index in range(1472):
            self.pool[index]=self.guarded[index+1]=index&255
        self.request(2,[8,1,88,0,63,0,0,0],0)
        self.request(2,[9,1,0,0,3,1,2,3],0)
        self.request(3,[8,1,8,0,1,0,0,0],0)
        self.discard(0);self.discard(1)
        self.assertEqual(bytes(self.pool[8:11]),b'\1\2\3')
        self.request(0,[8,1,8,0,2,0,0,0],0)
        self.request(2,[9,1,3,0,1,4],0)
        self.request(2,[11,1],0)
        self.request(3,[9,1,0,0,1,255],0)
        self.request(3,[10,1],0)
        self.discard(0);self.discard(3)

    def test_fuzz_valid_and_rejected_transactions(self):
        rng=random.Random(5503)
        for _ in range(1200):
            index=rng.randrange(6)
            if rng.randrange(8)==0:
                self.discard(index);continue
            op=rng.choice((8,9,9,9,10,11,255))
            if op==8: p=[8,1,rng.randrange(1,256),0,rng.randrange(1,200),0,0,0]
            elif op==9:
                start=0
                if index<4 and self.lengths[1][index]&0xe000==0x6000:
                    off=sum(n&8191 for n in self.lengths[1][:index])
                    start=self.pool[off+6]|self.pool[off+7]<<8
                count=rng.randrange(1,20)
                p=[9,1,start&255,start>>8,count]+[0]*count
            else:p=[op,1]
            if rng.randrange(4)==0:
                p += [0]*(24-len(p));p[rng.randrange(2,24)]=rng.randrange(256)
            self.request(index,p)

    def test_paint_pixels_clipping_pending_images_and_compacted_peers(self):
        lib=self.libs[1]
        lib.udeks_retained_bitmap_paint.argtypes=[c.c_ubyte]
        canvas=(c.c_ubyte*64000).in_dll(lib,'bitmap_canvas')
        for width,height in ((9,7),(128,80),(160,100)):
            self.setUp();stride=(width+7)//8
            pixels=bytearray((i*37+1)&255 for i in range(stride*height))
            if width&7:
                for at in range(stride-1,len(pixels),stride):pixels[at]&=255<<(8-(width&7))
            self.request(3,[8,1,width,0,height,4,0,14],0)
            for at in range(0,len(pixels),19):
                data=pixels[at:at+19]
                self.request(3,[9,1,at&255,at>>8,len(data),*data],0)
            lib.udeks_retained_bitmap_paint(3)
            self.assertFalse(any(canvas))  # fully uploaded is still not committed
            self.request(3,[10,1],0)
            self.request(0,[8,1,8,0,1,0,0,0],0)  # relocate completed peer
            for x,y,clip in ((0,0,(0,0,320,200)), (260,155,(265,160,316,196))):
                canvas[:]=bytes(64000)
                c.c_uint.in_dll(lib,'udeks_graphics_origin_x').value=x
                c.c_ubyte.in_dll(lib,'udeks_graphics_origin_y').value=y
                for name,value in zip(('left','top','right','bottom'),clip):
                    c.c_uint.in_dll(lib,'bitmap_clip_'+name).value=value
                lib.udeks_retained_bitmap_paint(3)
                expected=bytearray(64000)
                for yy in range(height):
                    for xx in range(width):
                        px,py=x+4+xx,y+14+yy
                        if clip[0]<=px<clip[2] and clip[1]<=py<clip[3] and pixels[yy*stride+xx//8]&(128>>(xx%8)):
                            expected[py*320+px]=1
                self.assertEqual(bytes(canvas),bytes(expected))
            self.discard(3);canvas[:]=bytes(64000)
            for index in (0,1,3,4,255):lib.udeks_retained_bitmap_paint(index)
            self.assertFalse(any(canvas))

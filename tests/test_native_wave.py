# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from native_wave_probe import wave_paths
from native_worker_probe import expected_surface


class NativeWave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); path=Path(cls.tmp.name)/'wave.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-I'+str(ROOT/'user/include'),str(ROOT/'user/lib/wave_paths.c'),'-o',str(path)],check=True)
        cls.lib=c.CDLL(str(path))
        cls.lib.udeks_wave_paths.argtypes=[c.POINTER(c.c_byte),c.c_uint,c.c_ubyte,c.POINTER(c.c_ubyte)]
        cls.lib.udeks_wave_paths.restype=c.c_uint

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def encode(self,width,height):
        buf=(c.c_ubyte*1130)(*([0xa5]*1130))
        samples=(c.c_byte*525).from_buffer_copy(expected_surface())
        length=self.lib.udeks_wave_paths(samples,width,height,c.cast(c.byref(buf,1),c.POINTER(c.c_ubyte)))
        self.assertEqual((buf[0],buf[-1]),(0xa5,0xa5))
        return length,bytes(buf)[1:-1]

    def test_projection_preserves_every_edge_and_scales_to_client(self):
        for w in (48,72,104,176,255,256,280,320):
            for h in (48,88,112,146,190,200):
                length,data=self.encode(w,h)
                expected,edges=wave_paths(w,h)
                self.assertEqual(length,1128)
                self.assertEqual(data,expected)
                self.assertEqual(len(edges),524)
                for x,y,xx,yy in edges:
                    self.assertTrue(3<=x<=w-3 and 3<=xx<=w-3)
                    self.assertTrue(14<=y<h-2 and 14<=yy<h-2)

    def test_invalid_sizes_leave_output_untouched(self):
        for w,h in ((0,112),(47,112),(321,112),(65535,112),(176,0),(176,47),(176,201)):
            length,data=self.encode(w,h)
            self.assertEqual(length,0); self.assertEqual(data,bytes([0xa5])*1128)

    def test_client_never_calls_legacy_gate_or_fixed_slots(self):
        source=(ROOT/'user/bin/xwave_native.c').read_text()
        self.assertNotIn('UAPP',source[source.index('#include'):])
        self.assertNotIn('0xcf',source)
        self.assertIn('native_wave_rows<21',source)
        self.assertEqual(source.count('worker_request()'),1)
        self.assertIn('else if(event==UDEKS_GFX_RESIZED)',source)
        self.assertIn('UDEKS_GFX_PATHS',source)

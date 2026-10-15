# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate the wire contract and compare real worker C to a frozen waveform oracle."""
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class EngineProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        so=Path(cls.tmp.name)/'engine.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-DUDEKS_Z80_WORKER_HOST_TEST','-Iinclude','tests/fixtures/engine_protocol.c',
            'src/z80/worker.c','-o',str(so)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(so))
        cls.lib.engine_test_validate.argtypes=[c.c_void_p,c.c_uint8]
        cls.lib.engine_test_validate.restype=c.c_uint8
        cls.lib.engine_test_worker.argtypes=[c.c_uint8]*4
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def valid(self,p,n=8):return self.lib.engine_test_validate((c.c_uint8*len(p))(*p),n)
    def test_exact_envelope_version_sequence_and_kind(self):
        p=[1,1,1,0,4,250,7,8]
        self.assertEqual(self.valid(p),0)
        for n in (0,1,7,9,16):self.assertEqual(self.valid(p,n),71)
        for offset,value in ((0,0),(0,2),(1,0),(1,2),(1,5)):
            bad=p.copy();bad[offset]=value;self.assertEqual(self.valid(bad),71)
        p[2]=0;self.assertEqual(self.valid(p),71)
        p[3]=1;self.assertEqual(self.valid(p),0)
    def test_operation_and_control_bounds(self):
        for kind in (3,4):
            p=[1,kind,1,0,0,0,0,0];self.assertEqual(self.valid(p),0)
            for i in range(4,8):
                bad=p.copy();bad[i]=1;self.assertEqual(self.valid(bad),22)
        self.assertEqual(self.valid([1,1,1,0,0,0,0,0]),0)
        for count in (0,9,25,64,255):self.assertEqual(self.valid([1,1,1,0,4,0,1,count]),22)
        for op in (1,2,3,5,255):self.assertEqual(self.valid([1,1,1,0,op,0,1,8]),38)
        for i in (5,6,7):
            p=[1,1,1,0,0,0,0,0];p[i]=1;self.assertEqual(self.valid(p),22)
    def test_real_worker_wave_against_frozen_waveform_oracle(self):
        output=(c.c_uint8*64).in_dll(self.lib,'udeks_worker_output')
        mailbox=(c.c_uint8*64).in_dll(self.lib,'udeks_worker_mailbox')
        # Frozen existing wave ABI; deliberately not parsed from worker source.
        wave=(0,3,6,9,12,14,17,19,21,23,25,26,28,29,29,30,
              30,30,29,29,28,26,25,23,21,19,17,14,12,9,6,3,
              0,-3,-6,-9,-12,-14,-17,-19,-21,-23,-25,-26,-28,-29,-29,-30,
              -30,-30,-29,-29,-28,-26,-25,-23,-21,-19,-17,-14,-12,-9,-6,-3)
        for phase in range(256):
            for step in (0,1,7,255):
                for count in range(1,9):
                    self.lib.engine_test_worker(4,phase,step,count)
                    expected=bytes(wave[((phase+i*step)&255)>>2]&255 for i in range(count))
                    self.assertEqual(bytes(output[:count]),expected,(phase,step,count))
                    self.assertEqual(bytes(output[count:]),bytes([165])*(64-count))
                    self.assertEqual((mailbox[6],mailbox[10],mailbox[18],mailbox[19]),(3,0,(phase+count*step)&255,0))
    def test_nop_preserves_worker_output(self):
        self.lib.engine_test_worker(0,0,0,0)
        self.assertEqual(bytes((c.c_uint8*64).in_dll(self.lib,'udeks_worker_output')),bytes([165])*64)

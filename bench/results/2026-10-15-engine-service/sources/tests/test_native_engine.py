# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class NativeEngineSDK(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();so=Path(cls.tmp.name)/'engine.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-Iuser/include','-Iinclude',
            'user/lib/native_engine.c','tests/fixtures/native_engine.c','-o',str(so)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(so));cls.lib.udeks_engine_wave.argtypes=[c.c_uint8,c.c_uint8,c.c_uint8,c.c_void_p,c.POINTER(c.c_uint)]
        cls.lib.udeks_engine_wave.restype=c.c_uint8
        for name in ('nop','stop'):getattr(cls.lib,'udeks_engine_'+name).restype=c.c_uint8
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.lib.engine_test_reset();self.data=(c.c_uint8*10)(*([165]*10));self.result=c.c_uint(0xabcd)
    def val(self,name,kind=c.c_uint8):return kind.in_dll(self.lib,name)
    def wave(self):return self.lib.udeks_engine_wave(250,7,8,c.byref(self.data,1),c.byref(self.result))
    def untouched(self):self.assertEqual(bytes(self.data),bytes([165])*10);self.assertEqual(self.result.value,0xabcd)
    def test_copied_outputs_request_sequence_and_owned_close(self):
        self.assertEqual(self.wave(),0);self.assertEqual(bytes(self.data),b'\xa5'+bytes(range(16,24))+b'\xa5');self.assertEqual(self.result.value,50)
        wire=bytes((c.c_uint8*8).in_dll(self.lib,'engine_test_sent'));self.assertEqual(wire[:2],b'\x01\x01');self.assertNotEqual(wire[2:4],b'\0\0');self.assertEqual(wire[4:],b'\x04\xfa\x07\x08')
        self.assertEqual(self.val('engine_test_closes',c.c_uint).value,1)
    def test_invalid_arguments_never_send(self):
        for count in (0,9,255):self.assertEqual(self.lib.udeks_engine_wave(0,1,count,self.data,c.byref(self.result)),255)
        for buffer,result in ((None,c.byref(self.result)),(self.data,None)):
            self.assertEqual(self.lib.udeks_engine_wave(0,1,1,buffer,result),255)
        self.untouched();self.assertEqual(self.val('engine_test_lookups',c.c_uint).value,0)
    def test_missing_server_contention_stale_peer_and_cleanup_failure(self):
        for mode,error in ((1,2),(2,28),(5,9),(9,5),(8,38),(10,5)):
            self.lib.engine_test_reset();self.val('engine_test_mode').value=mode
            self.assertEqual(self.wave(),255);self.assertEqual(self.val('udeks_errno').value,error);self.untouched()
    def test_full_queue_waits_before_send_and_accepted_work_is_not_replayed(self):
        self.val('engine_test_mode').value=4;self.assertEqual(self.wave(),0);self.assertEqual(self.val('engine_test_sends',c.c_uint).value,3)
        self.setUp();self.val('engine_test_mode').value=6;self.assertEqual(self.wave(),255);self.assertEqual(self.val('engine_test_sends',c.c_uint).value,1);self.assertEqual(self.val('engine_test_sleeps',c.c_uint).value,600);self.untouched()
        self.setUp();self.val('engine_test_mode').value=3;self.assertEqual(self.wave(),255);self.assertEqual(self.val('engine_test_sends',c.c_uint).value,600);self.untouched()
    def test_foreign_truncated_or_malformed_reply_preserves_outputs(self):
        for mode in (7,11):
            self.setUp();self.val('engine_test_mode').value=mode;self.assertEqual(self.wave(),255);self.assertEqual(self.val('udeks_errno').value,71);self.untouched()
        for offset,value in ((0,0),(1,4),(2,0),(3,255),(6,1),(7,9),(4,255)):
            self.setUp();self.val('engine_test_bad_offset').value=offset;self.val('engine_test_bad_value').value=value
            self.assertEqual(self.wave(),255);self.assertEqual(self.val('udeks_errno').value,71);self.untouched()
    def test_nop_and_shutdown_ack_remain_alive_until_server_disappears(self):
        self.assertEqual(self.lib.udeks_engine_nop(),0)
        self.setUp();self.assertEqual(self.lib.udeks_engine_stop(),0)
        request=bytes((c.c_uint8*8).in_dll(self.lib,'engine_test_sent'));ack=bytes((c.c_uint8*8).in_dll(self.lib,'engine_test_ack'))
        self.assertEqual(ack,request[:1]+b'\x04'+request[2:]);self.assertEqual(self.val('engine_test_sends',c.c_uint).value,2);self.assertEqual(self.val('engine_test_lookups',c.c_uint).value,2)
        self.setUp();self.val('engine_test_mode').value=12;self.assertEqual(self.lib.udeks_engine_stop(),255);self.assertEqual(self.val('udeks_errno').value,11)

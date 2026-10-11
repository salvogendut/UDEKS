# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class NativeIpcSDK(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='udeks-native-ipc-')
        so=Path(cls.tmp.name)/'ipc.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-DUDEKS_NATIVE_IPC_HOST_TEST','-Iuser/include','-Iinclude','user/lib/native_ipc.c',
            'tests/fixtures/native_ipc.c','-o',str(so)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(so))
        for name in ('create','lookup'):
            fn=getattr(cls.lib,'udeks_ipc_'+name);fn.argtypes=[c.c_char_p];fn.restype=c.c_uint
        cls.lib.udeks_ipc_send.argtypes=[c.c_uint,c.c_uint,c.c_void_p,c.c_uint8]
        cls.lib.udeks_ipc_receive.argtypes=[c.c_uint,c.POINTER(c.c_uint),c.c_void_p,c.c_uint8]
        cls.lib.udeks_ipc_close.argtypes=[c.c_uint]
        for name in ('send','receive','close'):getattr(cls.lib,'udeks_ipc_'+name).restype=c.c_uint8
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def value(self,name,kind=c.c_uint8):return kind.in_dll(self.lib,name)
    def setUp(self):
        for name in ('ipc_test_error','udeks_errno'):self.value(name).value=0
        self.value('ipc_test_calls',c.c_uint).value=0
        for name in ('ipc_test_bad_offset','ipc_test_reply_count','ipc_test_result_count','ipc_test_reply_state'):
            self.value(name).value=255
        self.value('ipc_test_data_count').value=4
        self.value('ipc_test_handle',c.c_uint).value=0x1234
        self.value('ipc_test_sender',c.c_uint).value=0x4321
    def sent(self):return bytes((c.c_uint8*24).in_dll(self.lib,'ipc_test_sent'))
    def errno(self):return self.value('udeks_errno').value
    def calls(self):return self.value('ipc_test_calls',c.c_uint).value
    def test_name_bounds_wire_version_and_handle_word(self):
        for action,name in enumerate(('create','lookup')):
            for endpoint in (b'a',b'12345678',b'~!Ab-_.z'):
                self.assertEqual(getattr(self.lib,'udeks_ipc_'+name)(endpoint),0x1234)
                self.assertEqual(self.value('ipc_test_action').value,action)
                self.assertEqual(self.value('ipc_test_count').value,len(endpoint))
                self.assertEqual(self.sent()[:len(endpoint)],endpoint)
                record=bytes((c.c_uint8*38).in_dll(self.lib,'ipc_test_record'))
                self.assertEqual(record[:8],b'UTRQ\0\x15\x02\x1d')
                self.assertEqual(self.errno(),0)
    def test_invalid_names_are_rejected_without_request(self):
        for name in (None,b'',b'123456789',b'white space',b'a\x7f',b'\x80',b'\x1f'):
            for function in (self.lib.udeks_ipc_create,self.lib.udeks_ipc_lookup):
                self.assertEqual(function(name),0)
                self.assertEqual(self.errno(),22)
        self.assertEqual(self.calls(),0)
    def test_binary_send_is_copied_once_and_no_retry_on_full_queue(self):
        data=(c.c_uint8*16)(*range(0,256,17))
        self.assertEqual(self.lib.udeks_ipc_send(0xabcd,0x1234,data,16),0)
        self.assertEqual(self.sent()[:20],b'\xcd\xab\x34\x12'+bytes(data))
        self.assertEqual(self.value('ipc_test_count').value,20)
        self.value('ipc_test_error').value=11
        self.assertEqual(self.lib.udeks_ipc_send(1,2,data,1),255)
        self.assertEqual(self.errno(),11);self.assertEqual(self.calls(),2)
    def test_bad_send_arguments_do_not_submit(self):
        data=(c.c_uint8*17)()
        for dest,source,buffer,count,error in ((0,1,data,1,9),(1,0,data,1,9),
            (1,2,None,1,22),(1,2,data,0,22),(1,2,data,17,22)):
            self.assertEqual(self.lib.udeks_ipc_send(dest,source,buffer,count),255)
            self.assertEqual(self.errno(),error)
        self.assertEqual(self.calls(),0)
    def test_receive_copies_owned_bytes_and_sender_after_validation(self):
        data=(c.c_uint8*18)(*([165]*18));sender=c.c_uint(0xaaaa)
        self.value('ipc_test_data_count').value=16
        self.assertEqual(self.lib.udeks_ipc_receive(0x2468,c.byref(sender),c.byref(data,1),16),16)
        self.assertEqual(bytes(data),b'\xa5'+bytes(range(0,256,17))+b'\xa5')
        self.assertEqual(sender.value,0x4321)
        self.assertEqual(self.sent()[:3],b'\x68\x24\x10')
    def test_receive_error_keeps_all_outputs_and_does_not_retry(self):
        for error in (9,11,13,90):
            self.setUp();data=(c.c_uint8*16)(*([165]*16));sender=c.c_uint(0xaaaa)
            self.value('ipc_test_error').value=error
            self.assertEqual(self.lib.udeks_ipc_receive(1,c.byref(sender),data,16),255)
            self.assertEqual(self.errno(),error);self.assertEqual(self.calls(),1)
            self.assertEqual(bytes(data),b'\xa5'*16);self.assertEqual(sender.value,0xaaaa)
        self.setUp();self.value('ipc_test_error').value=90;sender=c.c_uint(0xaaaa)
        self.assertEqual(self.lib.udeks_ipc_receive(1,c.byref(sender),None,0),255)
        self.assertEqual(self.errno(),90);self.assertEqual(self.calls(),1)
    def test_bad_receive_arguments_do_not_submit(self):
        data=(c.c_uint8*16)();sender=c.c_uint(0xaaaa)
        for handle,origin,buffer,cap,error in ((0,c.byref(sender),data,16,9),
            (1,None,data,16,22),(1,c.byref(sender),None,1,22),(1,c.byref(sender),data,17,22)):
            self.assertEqual(self.lib.udeks_ipc_receive(handle,origin,buffer,cap),255)
            self.assertEqual(self.errno(),error)
        self.assertEqual(self.calls(),0);self.assertEqual(sender.value,0xaaaa)
    def test_corrupt_envelope_is_rejected_before_copy(self):
        for offset,bad in ((0,0),(1,0),(2,0),(3,0),(4,1),(5,20),(6,1),
                           (7,23),(8,0),(9,4),(10,255),(11,0),(12,5),(13,1)):
            with self.subTest(offset=offset):
                self.setUp();data=(c.c_uint8*16)(*([165]*16));sender=c.c_uint(0xaaaa)
                self.value('ipc_test_bad_offset').value=offset;self.value('ipc_test_bad_value').value=bad
                self.assertEqual(self.lib.udeks_ipc_receive(1,c.byref(sender),data,16),255)
                self.assertEqual(self.errno(),71);self.assertEqual(self.calls(),1)
                self.assertEqual(bytes(data),b'\xa5'*16);self.assertEqual(sender.value,0xaaaa)
    def test_invalid_receive_lengths_and_zero_sender_fail_closed(self):
        for count in (0,2,5,19,24):
            self.setUp();data=(c.c_uint8*2)(165,165);sender=c.c_uint(0xaaaa)
            self.value('ipc_test_reply_count').value=count;self.value('ipc_test_result_count').value=count
            self.assertEqual(self.lib.udeks_ipc_receive(1,c.byref(sender),data,2),255)
            self.assertEqual(self.errno(),71);self.assertEqual(bytes(data),b'\xa5'*2);self.assertEqual(sender.value,0xaaaa)
        self.setUp();self.value('ipc_test_sender',c.c_uint).value=0
        data=(c.c_uint8*16)(*([165]*16));sender=c.c_uint(0xaaaa)
        self.assertEqual(self.lib.udeks_ipc_receive(1,c.byref(sender),data,16),255)
        self.assertEqual(bytes(data),b'\xa5'*16);self.assertEqual(sender.value,0xaaaa)
    def test_handle_reply_and_close_results_are_validated(self):
        self.assertEqual(self.lib.udeks_ipc_close(0),255);self.assertEqual(self.calls(),0)
        self.assertEqual(self.lib.udeks_ipc_close(0x1234),0);self.assertEqual(self.sent()[:2],b'\x34\x12')
        self.value('ipc_test_reply_count').value=1;self.value('ipc_test_result_count').value=1
        self.assertEqual(self.lib.udeks_ipc_close(1),255);self.assertEqual(self.errno(),71)
        self.assertEqual(self.lib.udeks_ipc_create(b'abc'),0);self.assertEqual(self.errno(),71)
        self.setUp();self.value('ipc_test_handle',c.c_uint).value=0
        self.assertEqual(self.lib.udeks_ipc_lookup(b'abc'),0);self.assertEqual(self.errno(),71)
    def test_malformed_error_envelopes_are_protocol_errors(self):
        for name,value in (('ipc_test_error',0),('ipc_test_reply_count',0),('ipc_test_result_count',1)):
            self.setUp();self.value('ipc_test_error').value=11;self.value('ipc_test_reply_state').value=128
            self.value(name).value=value
            self.assertEqual(self.lib.udeks_ipc_close(1),255);self.assertEqual(self.errno(),71)

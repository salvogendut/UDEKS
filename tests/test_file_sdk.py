# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FileSDK(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name)/'sdk.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-D__fastcall__=','-DUDEKS_FS_CLIENT_TEST','-I'+str(ROOT/'include'),
            '-I'+str(ROOT/'user/include'),str(ROOT/'user/lib/filesystem.c'),
            str(ROOT/'user/lib/filesystem_meta.c'),str(ROOT/'tests/fixtures/file_sdk.c'),
            '-o',str(path)],check=True)
        cls.lib=c.CDLL(str(path))
        for name in ('read','write_bytes','getdents'):
            f=getattr(cls.lib,'udeks_'+name)
            f.argtypes=[c.c_uint8,c.c_void_p,c.c_uint8]; f.restype=c.c_uint8
        cls.lib.udeks_open.argtypes=[c.c_char_p,c.c_uint8]
        cls.lib.udeks_stat.argtypes=[c.c_char_p,c.c_void_p]
        for name in ('open','close','stat'):
            getattr(cls.lib,'udeks_'+name).restype=c.c_uint8
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def value(self,name): return c.c_uint8.in_dll(self.lib,name)
    def setUp(self):
        for name in ('test_calls','test_result','test_error','udeks_errno'):
            self.value(name).value=0
    def test_open_path_bounds_and_count(self):
        for path in (None,b'',b'X'*24):
            self.assertEqual(self.lib.udeks_open(path,3),255)
        self.assertEqual(self.value('test_calls').value,0)
        self.value('test_result').value=4
        self.assertEqual(self.lib.udeks_open(b'/binary',3),4)
        self.assertEqual([self.value(n).value for n in ('test_op','test_fd','test_count')],[6,3,7])
        self.assertEqual(bytes((c.c_uint8*24).in_dll(self.lib,'test_payload'))[:8],b'/binary\0')
    def test_binary_and_short_write_are_not_retried(self):
        data=(c.c_uint8*4)(0,255,0,128)
        self.value('test_result').value=2
        self.assertEqual(self.lib.udeks_write_bytes(4,data,4),2)
        self.assertEqual(self.value('test_calls').value,1)
        self.assertEqual(bytes((c.c_uint8*24).in_dll(self.lib,'test_payload'))[:4],bytes(data))
        self.assertEqual(self.value('test_op').value,2)
    def test_null_and_oversized_transfers_do_not_submit(self):
        buffer=(c.c_uint8*25)()
        for name in ('read','write_bytes','getdents'):
            f=getattr(self.lib,'udeks_'+name)
            self.assertEqual(f(4,None,1),255)
            self.assertEqual(f(4,buffer,25),255)
        self.assertEqual(self.value('test_calls').value,0)
        self.assertEqual(self.value('udeks_errno').value,22)
    def test_zero_count_is_valid_with_null_buffer(self):
        for name in ('read','write_bytes'):
            self.assertEqual(getattr(self.lib,'udeks_'+name)(4,None,0),0)
        self.assertEqual(self.value('test_calls').value,2)
    def test_read_binary_and_guard_against_oversized_reply(self):
        (c.c_uint8*24).in_dll(self.lib,'udeks_file_payload')[:4]=[0,255,13,10]
        self.value('test_result').value=4
        buffer=(c.c_uint8*5)(99,99,99,99,99)
        self.assertEqual(self.lib.udeks_read(4,buffer,4),4)
        self.assertEqual(bytes(buffer),b'\0\xff\r\nc')
        self.value('test_result').value=5
        self.assertEqual(self.lib.udeks_read(4,buffer,4),255)
        self.assertEqual(self.value('udeks_errno').value,5)
        self.assertEqual(buffer[4],99)
    def test_error_and_close_are_not_hidden(self):
        self.value('test_result').value=255
        self.value('test_error').value=28
        self.assertEqual(self.lib.udeks_close(4),255)
        self.assertEqual(self.value('udeks_errno').value,28)
        self.assertEqual(self.value('test_op').value,9)
    def test_stat_size_and_null_validation(self):
        status=(c.c_uint8*3)()
        self.assertEqual(self.lib.udeks_stat(b'/file',None),255)
        self.assertEqual(self.value('test_calls').value,0)
        self.value('test_result').value=4
        self.assertEqual(self.lib.udeks_stat(b'/file',status),255)
        self.assertEqual(self.value('udeks_errno').value,5)


if __name__ == '__main__': unittest.main()

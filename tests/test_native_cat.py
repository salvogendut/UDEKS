# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class NativeCat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='udeks-cat-')
        binary=Path(cls.temp.name)/'cat.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-DUDEKS_NATIVE_CONSOLE_HOST_TEST','-Iuser/include','-Iinclude',
            'user/bin/cat.c','user/lib/native_console.c','user/lib/native_input.c',
            'user/lib/native_files.c','tests/fixtures/native_cat.c','-o',str(binary)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(binary))
        cls.lib.udeks_program_main.argtypes=[c.c_uint8,c.POINTER(c.c_char_p)]
        cls.lib.udeks_program_main.restype=c.c_uint8
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self): self.lib.cat_reset()
    def count(self,name): return c.c_uint.in_dll(self.lib,'cat_'+name).value
    def mode(self,value): c.c_uint8.in_dll(self.lib,'cat_mode').value=value
    def close_error(self,value): c.c_uint8.in_dll(self.lib,'cat_close_error').value=value
    def data(self,data):
        c.c_uint.in_dll(self.lib,'cat_size').value=len(data)
        (c.c_uint8*256).in_dll(self.lib,'cat_data')[:len(data)]=data
    def output(self,name,size): return bytes((c.c_uint8*256).in_dll(self.lib,'cat_'+name))[:self.count(size)]
    def run_cat(self,*args): return self.lib.udeks_program_main(len(args),(c.c_char_p*(len(args)+1))(*args,None))

    def test_empty_and_binary_chunks_yield_then_close_exactly_once(self):
        for size in (0,1,23,24,25,55,256):
            self.setUp(); data=bytes(range(size)); self.data(data)
            self.assertEqual(self.run_cat(b'cat',b'/data'),0)
            self.assertEqual(self.output('output','written'),data)
            self.assertEqual(self.count('closes'),1)
            self.assertEqual(self.count('sleeps'),(size+23)//24)
            self.assertEqual(self.count('reads'),(size+23)//24+1)

    def test_usage_and_missing_file_do_not_close_unowned_handle(self):
        self.assertEqual(self.run_cat(b'cat'),2)
        self.assertEqual(self.count('opens'),0)
        self.assertEqual(self.output('error','errors'),b'cat FILE\n')
        self.setUp(); self.mode(1)
        self.assertEqual(self.run_cat(b'cat',b'/missing'),1)
        self.assertEqual(self.count('closes'),0)
        self.assertEqual(self.output('error','errors'),b'cat: No such file or directory\n')

    def test_read_short_output_sleep_failures_close_and_never_retry(self):
        for mode in (2,3,4):
            self.setUp(); self.mode(mode); self.data(bytes(range(55)))
            self.assertEqual(self.run_cat(b'cat',b'/data'),1)
            self.assertEqual(self.count('closes'),1)
            self.assertEqual(self.count('reads'),2 if mode==2 else 1)
            self.assertEqual(self.count('written'),23 if mode==3 else 24)
            self.assertEqual(self.output('error','errors'),b'cat: I/O error\n')

    def test_close_failure_reported_but_does_not_replace_first_error(self):
        self.close_error(19)
        self.assertEqual(self.run_cat(b'cat',b'/empty'),1)
        self.assertEqual(self.output('error','errors'),b'cat: No such device\n')
        self.setUp(); self.mode(2); self.data(bytes(range(55))); self.close_error(19)
        self.assertEqual(self.run_cat(b'cat',b'/data'),1)
        self.assertEqual(self.output('error','errors'),b'cat: I/O error\n')

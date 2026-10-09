# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class UshStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        target=Path(cls.temp.name)/'ush.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-Iinclude','-Iuser/include','tests/fixtures/ush_status.c','-o',str(target)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(target)); cls.lib.test_command.argtypes=[c.c_char_p]
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self): self.lib.test_reset()
    def value(self,name,value): c.c_uint8.in_dll(self.lib,name).value=value
    def command(self,line):
        self.lib.test_command(line)
        return bytes((c.c_char*1024).in_dll(self.lib,'test_output')).split(b'\0',1)[0]
    def complete(self,status):
        self.value('test_submit_result',1)
        self.command(b'external arg')
        self.value('test_wait_result',1)
        self.lib.udeks_ush_poll()
        self.assertEqual(self.lib.test_status(),0)
        memory=(c.c_uint8*65536).in_dll(self.lib,'ush_test_memory')
        memory[0xf17a]=status
        self.value('test_wait_result',0); self.lib.udeks_ush_poll()
    def test_all_exit_bytes_and_echo_reset(self):
        for status in range(256):
            self.setUp(); self.complete(status)
            self.assertEqual(self.command(b'echo $?'),str(status).encode()+b'\n')
            self.assertEqual(self.command(b'echo $?'),b'0\n')
    def test_blank_preserves_status_but_regular_builtins_replace_it(self):
        self.complete(37); self.command(b'  ')
        self.assertEqual(self.lib.test_status(),37)
        self.assertEqual(self.command(b'echo not-$?'),b'not-$?\n')
        self.assertEqual(self.lib.test_status(),0)
        self.command(b'xinit nonsense')
        self.assertEqual(self.command(b'echo $?'),b'2\n')
    def test_failed_submit_and_builtin_cd_have_nonzero_status(self):
        self.value('test_submit_result',255)
        self.command(b'external')
        self.assertEqual(self.command(b'echo $?'),b'126\n')
        self.command(b'cd missing')
        self.assertEqual(self.command(b'echo $?'),b'1\n')


if __name__=='__main__': unittest.main()

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

    def queue_interrupt(self,task):
        self.value('test_submit_result',1)
        self.command(b'ticker hello')
        self.value('test_wait_result',1)
        memory=(c.c_uint8*65536).in_dll(self.lib,'ush_test_memory')
        memory[0xf3a0:0xf3a5]=bytes((165,task,3,0,0))
        self.lib.udeks_ush_poll()
        self.assertEqual(memory[0xf3a0],0)
        self.assertEqual(c.c_uint8.in_dll(self.lib,'test_prompts').value,0)
        return memory

    def test_parent_cancels_exact_child_once_and_waits_for_retirement(self):
        for task in range(3,7):
            self.setUp(); memory=self.queue_interrupt(task)
            self.assertEqual(bytes((c.c_uint8*6).in_dll(self.lib,'test_cancel_request')),bytes((14,0,3,task,0,130)))
            self.assertEqual(bytes((c.c_char*1024).in_dll(self.lib,'test_output')).split(b'\0')[0],b'Interrupted\n')
            self.lib.udeks_ush_poll()
            self.assertEqual(c.c_uint8.in_dll(self.lib,'test_cancel_calls').value,1)
            self.assertEqual(c.c_uint8.in_dll(self.lib,'test_prompts').value,0)
            memory[0xf17a]=130; self.value('test_wait_result',0); self.lib.udeks_ush_poll()
            self.assertEqual(self.command(b'echo $?'),b'130\n')

    def test_natural_exit_race_is_silent_and_preserves_actual_status(self):
        self.value('test_cancel_result',255); self.value('test_cancel_errno',3)
        memory=self.queue_interrupt(6)
        self.assertEqual(bytes((c.c_char*1024).in_dll(self.lib,'test_output')).split(b'\0')[0],b'')
        memory[0xf17a]=37; self.value('test_wait_result',0); self.lib.udeks_ush_poll()
        self.assertEqual(self.command(b'echo $?'),b'37\n')

    def test_other_cancellation_failure_is_reported_without_false_completion(self):
        self.value('test_cancel_result',255); self.value('test_cancel_errno',22)
        self.queue_interrupt(6)
        self.assertEqual(bytes((c.c_char*1024).in_dll(self.lib,'test_output')).split(b'\0')[0],b'Interrupt failed\n')
        self.assertEqual(c.c_uint8.in_dll(self.lib,'test_prompts').value,0)


if __name__=='__main__': unittest.main()

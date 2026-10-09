# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class NativeConsoleSDK(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='udeks-native-console-')
        binary=Path(cls.temp.name)/'sdk.so'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-DUDEKS_NATIVE_CONSOLE_HOST_TEST','-Iuser/include','-Iinclude',
            'user/lib/native_console.c','user/lib/native_input.c',
            'tests/fixtures/native_console.c','-o',str(binary)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(binary))
        cls.lib.udeks_write_bytes.argtypes=[c.c_uint8,c.c_void_p,c.c_uint8]
        cls.lib.udeks_write.argtypes=[c.c_uint8,c.c_char_p]
        cls.lib.udeks_write_byte.argtypes=[c.c_uint8,c.c_uint8]
        cls.lib.udeks_sleep.argtypes=[c.c_uint16]
        cls.lib.udeks_poll.argtypes=[c.c_uint8,c.c_uint16]
        cls.lib.udeks_read.argtypes=[c.c_uint8,c.c_void_p,c.c_uint8]
        for name in ('write_bytes','write','write_byte','sleep','read','poll'):
            getattr(cls.lib,'udeks_'+name).restype=c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def value(self,name): return c.c_uint8.in_dll(self.lib,name)
    def setUp(self):
        for name in ('test_mode','test_calls','udeks_errno','test_read_mode','test_read_count'): self.value(name).value=0
        self.value('test_poll_result').value=1
        c.c_uint16.in_dll(self.lib,'test_output_size').value=0
    def output(self):
        return bytes((c.c_uint8*256).in_dll(self.lib,'test_output'))[:c.c_uint16.in_dll(self.lib,'test_output_size').value]

    def test_string_is_copied_in_bounded_chunks_for_both_output_streams(self):
        for fd in (1,2):
            self.setUp()
            data=b'0123456789'*5
            self.assertEqual(self.lib.udeks_write(fd,data),0)
            self.assertEqual(self.output(),data)
            self.assertEqual(bytes((c.c_uint8*64).in_dll(self.lib,'test_counts'))[:3],bytes((24,24,2)))
            self.assertEqual(bytes((c.c_uint8*64).in_dll(self.lib,'test_fds'))[:3],bytes((fd,fd,fd)))

    def test_counted_binary_and_single_byte_preserve_zero_and_high_bit(self):
        data=(c.c_uint8*4)(0,255,13,128)
        self.assertEqual(self.lib.udeks_write_bytes(2,data,4),4)
        self.assertEqual(self.lib.udeks_write_byte(1,0),0)
        self.assertEqual(self.output(),bytes(data)+b'\0')

    def test_invalid_inputs_do_not_cross_gate(self):
        for fd in (0,3,255): self.assertEqual(self.lib.udeks_write_bytes(fd,b'a',1),255)
        self.assertEqual(self.value('udeks_errno').value,9)
        for count,data in ((25,b'x'*25),(1,None)):
            self.assertEqual(self.lib.udeks_write_bytes(1,data,count),255)
        self.assertEqual(self.lib.udeks_write(1,None),1)
        for ticks in (0,601,65535): self.assertEqual(self.lib.udeks_sleep(ticks),255)
        self.assertEqual(self.value('udeks_errno').value,22)
        self.assertEqual(self.value('test_calls').value,0)

    def test_zero_length_and_empty_string(self):
        self.assertEqual(self.lib.udeks_write_bytes(1,None,0),0)
        self.assertEqual(self.lib.udeks_write(2,b''),0)
        self.assertEqual(self.value('test_calls').value,1)

    def test_sleep_encodes_ticks_and_requires_owned_zero_result(self):
        for ticks in (1,255,256,600):
            self.assertEqual(self.lib.udeks_sleep(ticks),0)
            self.assertEqual([self.value(n).value for n in ('test_op','test_fd','test_count')],[13,0,2])
            self.assertEqual(bytes((c.c_uint8*24).in_dll(self.lib,'test_payload'))[:2],ticks.to_bytes(2,'little'))
        self.value('test_mode').value=3
        self.assertEqual(self.lib.udeks_sleep(1),255)
        self.assertEqual(self.value('udeks_errno').value,71)

    def test_short_or_failed_write_is_not_retried(self):
        self.value('test_mode').value=2
        self.assertEqual(self.lib.udeks_write_bytes(1,b'abc',3),2)
        self.assertEqual(self.lib.udeks_write(1,b'a'*50),1)
        self.assertEqual(self.value('udeks_errno').value,5)
        self.assertEqual(self.value('test_calls').value,2)
        self.value('test_mode').value=1
        self.assertEqual(self.lib.udeks_write(1,b'abc'),1)
        self.assertEqual(self.value('udeks_errno').value,5)
        self.assertEqual(self.value('test_calls').value,3)

    def test_malformed_and_unowned_replies_are_not_accepted(self):
        for mode in range(3,13):
            with self.subTest(mode=mode):
                self.value('test_mode').value=mode
                self.assertEqual(self.lib.udeks_write_bytes(1,b'abc',3),255)
                self.assertEqual(self.value('udeks_errno').value,71)

    def test_private_sequence_wraps_and_no_bank0_veneer_is_linked(self):
        self.lib.udeks_sleep(1)
        first=self.value('test_sequence').value
        for _ in range(256): self.assertEqual(self.lib.udeks_sleep(1),0)
        self.assertEqual(self.value('test_sequence').value,first)
        source=(ROOT/'user/lib/native_console_entry.s').read_text()
        self.assertIn('jmp $ff16',source)
        self.assertNotIn('jmp $cf',source.lower())
        builder=(ROOT/'tools/build_native_console.py').read_text()
        self.assertNotIn('udeks-8502.map',builder)
        self.assertNotIn('user/lib/syscall.s',builder)

    def test_input_checks_arguments_before_request_or_destination_mutation(self):
        data=(c.c_uint8*26)(*([165]*26))
        for fd in (1,2,3,255):
            self.assertEqual(self.lib.udeks_read(fd,data,1),255)
            self.assertEqual(self.lib.udeks_poll(fd,0),255)
            self.assertEqual(self.value('udeks_errno').value,9)
        for count,ptr in ((25,data),(1,None)):
            self.assertEqual(self.lib.udeks_read(0,ptr,count),255)
        for timeout in (601,65534): self.assertEqual(self.lib.udeks_poll(0,timeout),255)
        self.assertEqual(self.value('udeks_errno').value,22)
        self.assertEqual(self.lib.udeks_read(0,None,0),0)
        self.assertEqual(self.value('udeks_errno').value,0)
        self.assertEqual(self.value('test_calls').value,0)
        self.assertEqual(bytes(data),b'\xa5'*26)

    def test_poll_encodes_bounds_and_checks_owned_response_payload(self):
        for timeout in (0,1,255,256,600,65535):
            self.assertEqual(self.lib.udeks_poll(0,timeout),1)
            self.assertEqual(bytes((c.c_uint8*24).in_dll(self.lib,'test_payload'))[:4],
                             b'\1\0'+timeout.to_bytes(2,'little'))
        self.value('test_poll_result').value=0
        self.assertEqual(self.lib.udeks_poll(0,0),0)
        self.assertEqual(self.lib.udeks_poll(0,65535),255)
        self.assertEqual(self.value('udeks_errno').value,71)
        self.value('test_poll_result').value=1
        for mode in (1,2,3,4):
            self.value('test_read_mode').value=mode
            self.assertEqual(self.lib.udeks_poll(0,65535),255)
            self.assertEqual(self.value('udeks_errno').value,71)

    def test_read_copies_only_valid_owned_bytes_after_blocking_poll(self):
        data=(c.c_uint8*26)(*([165]*26))
        source=(c.c_uint8*24).in_dll(self.lib,'test_input')
        source[:]=b'Abc 123\n'+b'\xff'*16
        self.value('test_read_count').value=8
        self.assertEqual(self.lib.udeks_read(0,c.byref(data,1),24),8)
        self.assertEqual(bytes(data),b'\xa5Abc 123\n'+b'\xa5'*17)
        self.assertEqual(self.value('test_calls').value,2)

    def test_failed_or_malformed_input_never_copies_or_retries(self):
        for mode,error,calls in ((1,71,1),(5,5,1),(6,71,2),(7,11,2)):
            self.setUp()
            data=(c.c_uint8*2)(165,165)
            self.value('test_read_mode').value=mode
            self.assertEqual(self.lib.udeks_read(0,data,2),255)
            self.assertEqual(self.value('udeks_errno').value,error)
            self.assertEqual(self.value('test_calls').value,calls)
            self.assertEqual(bytes(data),b'\xa5'*2)
        self.setUp(); self.value('test_read_count').value=3
        self.assertEqual(self.lib.udeks_read(0,data,2),255)
        self.assertEqual(self.value('udeks_errno').value,71)
        self.assertEqual(bytes(data),b'\xa5'*2)


if __name__=='__main__': unittest.main()

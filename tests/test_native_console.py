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
            'user/lib/native_console.c','user/lib/native_input.c','user/lib/native_files.c',
            'tests/fixtures/native_console.c','-o',str(binary)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(binary))
        cls.lib.udeks_write_bytes.argtypes=[c.c_uint8,c.c_void_p,c.c_uint8]
        cls.lib.udeks_write.argtypes=[c.c_uint8,c.c_char_p]
        cls.lib.udeks_write_byte.argtypes=[c.c_uint8,c.c_uint8]
        cls.lib.udeks_sleep.argtypes=[c.c_uint16]
        cls.lib.udeks_poll.argtypes=[c.c_uint8,c.c_uint16]
        cls.lib.udeks_read.argtypes=[c.c_uint8,c.c_void_p,c.c_uint8]
        cls.lib.udeks_open.argtypes=[c.c_char_p,c.c_uint8]
        cls.lib.udeks_close.argtypes=[c.c_uint8]
        for name in ('write_bytes','write','write_byte','sleep','read','poll','open','close'):
            getattr(cls.lib,'udeks_'+name).restype=c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def value(self,name): return c.c_uint8.in_dll(self.lib,name)
    def setUp(self):
        for name in ('test_mode','test_calls','udeks_errno','test_read_mode','test_read_count',
                     'test_close_result','test_file_error'): self.value(name).value=0
        self.value('test_poll_result').value=1
        self.value('test_open_result').value=4
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
        for mode in range(3,14):
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

    def test_file_open_validates_path_and_mode_without_mutating_record(self):
        record=(c.c_uint8*38).in_dll(self.lib,'native_console_request')
        for path,mode in ((None,0),(b'',0),(b'a'*24,0),(b'file',1),(b'file',2),(b'file',4),(b'file',255)):
            record[:]=b'\xa5'*38
            self.assertEqual(self.lib.udeks_open(path,mode),255)
            self.assertEqual(self.value('udeks_errno').value,22)
            self.assertEqual(bytes(record),b'\xa5'*38)
        self.assertEqual(self.value('test_calls').value,0)

    def test_blocked_reply_identity_does_not_include_common_minor_byte(self):
        self.value('test_mode').value=13
        self.assertEqual(self.lib.udeks_sleep(1),0)
        self.assertEqual(self.lib.udeks_poll(0,1),1)

    def test_file_versions_and_paths_are_counted_with_nul(self):
        for path,mode,minor in ((b'/hello',0,8),(b'a'*23,0,8),(b'/new',3,14)):
            self.assertEqual(self.lib.udeks_open(path,mode),4)
            self.assertEqual([self.value(n).value for n in ('test_op','test_fd','test_count','test_minor')],
                             [6,mode,len(path),minor])
            self.assertEqual(bytes((c.c_uint8*24).in_dll(self.lib,'test_payload'))[:len(path)+1],path+b'\0')
        self.assertEqual(self.lib.udeks_write_bytes(4,b'\x00\xff\x80',3),3)
        self.assertEqual(self.value('test_minor').value,14)
        self.assertEqual(self.lib.udeks_close(4),0)
        self.assertEqual([self.value(n).value for n in ('test_op','test_fd','test_count')],[9,4,0])

    def test_file_read_does_not_poll_and_copies_only_owned_result(self):
        buffer=(c.c_uint8*26)(*([165]*26))
        data=(c.c_uint8*24).in_dll(self.lib,'test_input'); data[:]=bytes(range(24))
        self.value('test_read_count').value=24
        self.assertEqual(self.lib.udeks_read(4,c.byref(buffer,1),24),24)
        self.assertEqual(bytes(buffer),b'\xa5'+bytes(range(24))+b'\xa5')
        self.assertEqual(self.value('test_calls').value,1)
        self.assertEqual(self.value('test_op').value,1)
        self.value('test_read_count').value=0
        self.assertEqual(self.lib.udeks_read(4,buffer,24),0)
        self.assertEqual(self.lib.udeks_poll(4,0),255)
        self.assertEqual(self.value('udeks_errno').value,9)
        for error in (5,9,19):
            before=bytes(buffer); self.value('test_file_error').value=error
            self.assertEqual(self.lib.udeks_read(4,buffer,24),255)
            self.assertEqual(bytes(buffer),before)
            self.assertEqual(self.value('udeks_errno').value,error)

    def test_file_errors_short_writes_and_close_are_never_retried(self):
        for error in (2,5,16,17,19,21,24,28,30):
            self.setUp(); self.value('test_file_error').value=error
            self.assertEqual(self.lib.udeks_open(b'/data',0),255)
            self.assertEqual(self.value('udeks_errno').value,error)
            self.assertEqual(self.value('test_calls').value,1)
        self.setUp(); self.value('test_mode').value=2
        self.assertEqual(self.lib.udeks_write_bytes(4,b'abc',3),2)
        self.assertEqual(self.value('test_calls').value,1)
        self.setUp(); self.value('test_file_error').value=5
        self.assertEqual(self.lib.udeks_close(4),255)
        self.assertEqual(self.value('udeks_errno').value,5)
        self.assertEqual(self.value('test_calls').value,1)

    def test_file_reply_validation_and_bootfs_directory_release(self):
        for fd in (0,1,2,5,254):
            self.setUp(); self.value('test_open_result').value=fd
            self.assertEqual(self.lib.udeks_open(b'/file',0),255)
            self.assertEqual(self.value('udeks_errno').value,71)
        self.setUp(); self.value('test_open_result').value=3
        self.assertEqual(self.lib.udeks_open(b'/',0),255)
        self.assertEqual(self.value('udeks_errno').value,21)
        self.assertEqual(self.value('test_calls').value,2)
        self.assertEqual((self.value('test_op').value,self.value('test_fd').value),(9,3))
        self.setUp(); self.value('test_close_result').value=1
        self.assertEqual(self.lib.udeks_close(4),255)
        self.assertEqual(self.value('udeks_errno').value,71)
        for fd in (0,1,2,3,255): self.assertEqual(self.lib.udeks_close(fd),255)


if __name__=='__main__': unittest.main()

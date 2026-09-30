# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Sysinfo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        target = Path(cls.temp.name)/'sysinfo.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
            '-D__fastcall__=', '-DUDEKS_SYSINFO_HOST_TEST', '-I'+str(ROOT/'include'),
            '-I'+str(ROOT/'user/include'), str(ROOT/'user/bin/sysinfo.c'),
            str(ROOT/'tests/fixtures/sysinfo_client.c'), '-o', str(target)], check=True)
        cls.lib = c.CDLL(str(target))
        cls.lib.udeks_program_main.argtypes = [c.c_uint8, c.POINTER(c.c_char_p)]
        cls.lib.udeks_program_main.restype = c.c_uint8
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self): self.lib.test_reset()
    def invoke(self, *args):
        return self.lib.udeks_program_main(len(args), (c.c_char_p*(len(args)+1))(
            *(a.encode() for a in args), None))
    def output(self, name='output', size=1024):
        return bytes((c.c_uint8*size).in_dll(self.lib, 'test_'+name))[:
            c.c_uint16.in_dll(self.lib, 'test_'+name+'_length').value].decode()
    def test_free_distinguishes_physical_video_and_allocatable_memory(self):
        self.assertEqual(self.invoke('/mnt/FREE'), 0)
        self.assertIn('CPU RAM: 128 KiB; VDC RAM: 64 KiB (video only)', self.output())
        self.assertIn('total 2560  used 0  free 2560', self.output())
        self.assertIn('not total unused physical RAM', self.output())
        self.setUp()
        (c.c_uint8*16).in_dll(self.lib, 'sysinfo_tasks')[9] = 2
        self.assertEqual(self.invoke('free'), 0)
        self.assertIn('total 2560  used 2560  free 0', self.output())
    def test_df_uses_statfs_and_reports_blocks(self):
        (c.c_uint8*8).in_dll(self.lib, 'test_result')[:] = b'\0\1\x98\2\x64\0\x08\1'
        self.assertEqual(self.invoke('df'), 0)
        self.assertIn('664         564   100', self.output())
        self.assertIn('iec8', self.output())
        self.assertIn('Read-only mount', self.output())
    def test_errors_use_stderr_and_nonzero_exit(self):
        for error, text in ((2, 'not mounted'), (16, 'busy'), (5, 'read failed')):
            self.setUp(); c.c_uint8.in_dll(self.lib, 'sysinfo_error').value = error
            self.assertEqual(self.invoke('/mnt/DF', '/mnt'), 1)
            self.assertIn(text, self.output('error', 128))
            self.assertEqual(self.output(), '')
    def test_invalid_arguments_do_not_request_io(self):
        for args in (('free', '-a'), ('df', '/other'), ('df', '/mnt', 'extra')):
            self.assertEqual(self.invoke(*args), 1)
        self.assertEqual(c.c_uint8.in_dll(self.lib, 'test_calls').value, 0)

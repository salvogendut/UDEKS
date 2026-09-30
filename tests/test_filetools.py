# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FileTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        target = Path(cls.temp.name)/'filetools.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
            '-D__fastcall__=', '-DUDEKS_FILETOOLS_HOST_TEST', '-I'+str(ROOT/'include'),
            '-I'+str(ROOT/'user/include'), str(ROOT/'user/bin/filetools.c'),
            str(ROOT/'tests/fixtures/filetools_client.c'), '-o', str(target)], check=True)
        cls.lib = c.CDLL(str(target))
        cls.lib.udeks_program_main.argtypes = [c.c_uint8, c.POINTER(c.c_char_p)]
        cls.lib.udeks_program_main.restype = c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self): self.lib.test_reset()
    def test_explicit_uppercase_dos_paths(self):
        for command, args in (('/mnt/LS', ('/bin',)), ('/mnt/CAT', ('/mnt/HELLO',))):
            self.setUp()
            self.assertEqual(self.invoke(command, *args), 0)
    def byte(self, name): return c.c_uint8.in_dll(self.lib, 'test_'+name)
    def word(self, name): return c.c_uint16.in_dll(self.lib, 'test_'+name)
    def output(self, error=False):
        name, size = ('error', 128) if error else ('output', 1024)
        return bytes((c.c_uint8*size).in_dll(self.lib, 'test_'+name))[:self.word(name+'_length').value]
    def invoke(self, *args):
        argv = (c.c_char_p*(len(args)+1))(*(a.encode() for a in args), None)
        return self.lib.udeks_program_main(len(args), argv)

    def test_cat_is_an_exact_byte_stream_not_a_string_or_line_formatter(self):
        for sample in (b'', b'X', b'TEXT WITHOUT LF', bytes(range(24)), bytes(range(256))*2):
            self.setUp()
            (c.c_uint8*512).in_dll(self.lib, 'test_input')[:len(sample)] = sample
            self.word('length').value = len(sample)
            self.assertEqual(self.invoke('/bin/cat', '/mnt/HELLO'), 0)
            self.assertEqual(self.output(), sample)
            self.assertEqual(self.output(True), b'')
            self.assertEqual(self.byte('closes').value, 1)

    def test_cat_errors_close_once_and_use_stderr(self):
        for op, closes in ((6, 0), (1, 1), (9, 1)):
            self.setUp(); self.byte('failure_op').value = op
            self.assertEqual(self.invoke('cat', '/mnt/HELLO'), 1)
            self.assertEqual(self.byte('closes').value, closes)
            self.assertTrue(self.output(True).startswith(b'cat: '))
            self.assertEqual(self.output(), b'')

    def test_cat_missing_file_explains_enoent_not_every_open_failure(self):
        for error, message in ((2, b'cat: No such file or directory\n'),
                               (5, b'cat: open failed\n'),
                               (24, b'cat: open failed\n')):
            self.setUp()
            self.byte('failure_op').value = 6
            self.byte('errno').value = error
            self.assertEqual(self.invoke('cat', '/mnt/NOFILE'), 1)
            self.assertEqual(self.output(True), message)
            self.assertEqual(self.output(), b'')
            self.assertEqual(self.byte('closes').value, 0)

    def test_overlong_path_cannot_reuse_a_stale_enoent(self):
        c.c_uint8.in_dll(self.lib, 'filetools_error').value = 2
        self.assertEqual(self.invoke('cat', 'x'*24), 1)
        self.assertEqual(self.byte('calls').value, 0)
        self.assertEqual(c.c_uint8.in_dll(self.lib, 'filetools_error').value, 22)
        self.assertEqual(self.output(True), b'cat: open failed\n')

    def test_invalid_cli_arguments_do_not_issue_requests(self):
        for args in (('cat',), ('cat', 'a', 'b'), ('cat', 'x'*24), ('ls', 'a', 'b'),
                     ('mount',), ('mount', '7', '/mnt'), ('mount', '08', '/mnt'),
                     ('mount', '12', '/mnt'), ('mount', '8', '/mnt/x'), ('umount',)):
            self.assertEqual(self.invoke(*args), 1, args)
        self.assertEqual(self.byte('calls').value, 0)

    def test_mount_aliases_share_one_payload_contract(self):
        for device in range(8, 12):
            self.assertEqual(self.invoke('/bin/mount', str(device), '/mnt'), 0)
            self.assertEqual(self.byte('op').value, 17)
            self.assertEqual(self.byte('count').value, 5)
            self.assertEqual(bytes((c.c_uint8*24).in_dll(self.lib, 'test_payload'))[:5], bytes([device])+b'/mnt')
        self.assertEqual(self.invoke('/bin/umount', '/mnt'), 0)
        self.assertEqual((self.byte('op').value, self.byte('count').value), (18, 4))

    def test_ls_uses_requested_directory_for_metadata_and_current_directory(self):
        self.assertEqual(self.invoke('ls', '-l', '/mnt'), 0)
        self.assertEqual((c.c_char*24).in_dll(self.lib, 'test_stat_path').value, b'/mnt/HELLO')
        self.assertEqual(self.output(), b'-r-x 12 HELLO\n')
        for cwd, expected in ((0, b'/'), (1, b'/bin')):
            self.setUp(); c.c_uint8.in_dll(self.lib, 'filetools_cwd').value = cwd
            self.assertEqual(self.invoke('ls'), 0)
            self.assertEqual((c.c_char*24).in_dll(self.lib, 'test_open_path').value, expected)

    def test_ls_unknown_disk_size_is_not_bootfs_metadata(self):
        self.byte('failure_op').value = 8
        self.assertEqual(self.invoke('ls', '-l', '/mnt'), 0)
        self.assertEqual(self.output(), b'-r-x ? HELLO\n')

    def test_ls_metadata_path_join_stays_within_request_capacity(self):
        for length in (17, 18, 23):
            self.setUp()
            path = '/'+'a'*(length-1)
            self.assertEqual(self.invoke('ls', '-l', path), 0)
            self.assertEqual(self.output(), b'-r-x 12 HELLO\n' if length == 17 else b'-r-x ? HELLO\n')
            stat_path = (c.c_char*24).in_dll(self.lib, 'test_stat_path').value
            self.assertEqual(stat_path, (path+'/HELLO').encode() if length == 17 else b'')

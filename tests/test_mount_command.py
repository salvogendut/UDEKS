# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MountCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        library = Path(cls.tmp.name)/'mount.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                        '-D__fastcall__=', '-I'+str(ROOT/'include'), '-I'+str(ROOT/'user/include'),
                        str(ROOT/'user/bin/mount.c'), str(ROOT/'tests/fixtures/mount_client.c'),
                        '-o', str(library)], check=True)
        cls.lib = c.CDLL(str(library))
        cls.lib.udeks_program_main.argtypes = [c.c_uint8, c.POINTER(c.c_char_p)]
        cls.lib.udeks_program_main.restype = c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def value(self, name): return c.c_uint8.in_dll(self.lib, 'test_'+name)

    def setUp(self):
        self.value('calls').value = self.value('error').value = 0
        (c.c_char*80).in_dll(self.lib, 'test_message').value = b''

    def invoke(self, *args):
        argv = (c.c_char_p*(len(args)+1))(*(arg.encode() for arg in args), None)
        return self.lib.udeks_program_main(len(args), argv)

    def test_devices_and_alias(self):
        for device in range(8, 12):
            self.assertEqual(self.invoke('mount', str(device), '/mnt'), 0)
            self.assertEqual((self.value('device').value, self.value('operation').value), (device, 17))
        self.assertEqual(self.invoke('umount', '/mnt'), 0)
        self.assertEqual(self.value('operation').value, 18)
        self.assertEqual(self.invoke('/bin/umount', '/mnt'), 0)
        self.assertEqual(self.value('operation').value, 18)

    def test_bad_arguments_never_submit(self):
        for args in (('mount',), ('mount', '8'), ('mount', '', '/mnt'),
                     ('mount', '7', '/mnt'), ('mount', '12', '/mnt'),
                     ('mount', '1.', '/mnt'), ('mount', '1/', '/mnt'),
                     ('mount', '08', '/mnt'), ('mount', '80', '/mnt'),
                     ('mount', '8', '/mnt/x'), ('mount', '8', '/mnt', 'extra'),
                     ('umount',), ('umount', '8', '/mnt')):
            self.assertEqual(self.invoke(*args), 1, args)
        self.assertEqual(self.value('calls').value, 0)
        self.assertEqual(self.value('descriptor').value, 2)

    def test_error_returns_nonzero_and_uses_stderr(self):
        self.value('error').value = 5
        self.assertEqual(self.invoke('mount', '8', '/mnt'), 1)
        self.assertEqual(self.value('descriptor').value, 2)
        self.assertIn(b'failed', (c.c_char*80).in_dll(self.lib, 'test_message').value)

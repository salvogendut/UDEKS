# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Startup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        target = Path(cls.temp.name)/'startup.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
            '-DUDEKS_STARTUP_HOST_TEST', '-I'+str(ROOT/'include'), '-I'+str(ROOT/'user/include'),
            str(ROOT/'user/lib/startup.c'), str(ROOT/'tests/fixtures/startup_client.c'),
            '-o', str(target)], check=True)
        cls.lib = c.CDLL(str(target))
        cls.lib.udeks_startup_begin.restype = c.c_uint8
        cls.lib.udeks_startup_next.restype = c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self): self.lib.test_reset()
    def start(self, text):
        c.c_uint16.in_dll(self.lib, 'test_cursor').value = 0
        (c.c_uint8*300).in_dll(self.lib, 'test_input')[:len(text)] = text
        c.c_uint16.in_dll(self.lib, 'test_length').value = len(text)
        return self.lib.udeks_startup_begin(8)
    def lines(self):
        result = []; line = c.create_string_buffer(55)
        for _ in range(256):
            if not self.lib.udeks_startup_next(line): return result
            result.append(line.value)
        self.fail('unbounded parser')
    def calls(self): return (c.c_uint8*20).in_dll(self.lib, 'test_calls')

    def test_crlf_empty_lines_and_final_line(self):
        self.assertEqual(self.start(b'\r\n# comment\n\necho ready\r\nmount 8 /mnt'), 1)
        self.assertEqual(self.lines(), [b'# comment', b'echo ready', b'mount 8 /mnt'])
        self.assertEqual((self.calls()[9], self.calls()[18]), (1, 1))

    def test_file_and_line_limits_are_exact(self):
        for text, result in ((b'', 0), (b'X'*54, 1), (b'X'*55, 255),
                             (b'\n'*254+b'X', 1), (b'\n'*255+b'X', 255)):
            self.setUp(); self.assertEqual(self.start(text), result)
            self.assertEqual((self.calls()[9], self.calls()[18]), (1, 1))
            if result == 255: self.assertEqual(self.lines(), [])

    def test_invalid_later_line_prevents_any_execution(self):
        for tail in (b'\0', b'\x80', b'\x1b', b'X'*55):
            self.assertEqual(self.start(b'echo MUST-NOT-RUN\n'+tail), 255)
            self.assertEqual(self.lines(), [])
        self.assertEqual(self.start(b'\techo\tok'), 1)

    def test_absent_script_is_silent_and_errors_release_handles(self):
        for op, error, expected, closed, unmounted in ((6, 2, 0, 0, 1), (6, 5, 255, 0, 1),
                (1, 5, 255, 1, 1), (9, 5, 255, 1, 1), (18, 5, 255, 1, 1), (17, 5, 255, 0, 0)):
            self.setUp()
            c.c_uint8.in_dll(self.lib, 'test_fail_op').value = op
            c.c_uint8.in_dll(self.lib, 'test_error').value = error
            self.assertEqual(self.start(b'echo no'), expected)
            self.assertEqual(self.lines(), [])
            self.assertEqual((self.calls()[9], self.calls()[18]), (closed, unmounted))

    def test_default_script_fits_and_contains_only_comments(self):
        text = (ROOT/'user/etc/rc').read_bytes()
        self.assertLessEqual(len(text), 255)
        self.assertEqual(self.start(text), 1)
        self.assertTrue(all(line.startswith(b'#') for line in self.lines()))

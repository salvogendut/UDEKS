# SPDX-License-Identifier: GPL-3.0-or-later
"""cowsay renders the classic cow shape with bubble, thought and eyes."""
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Cowsay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        target = Path(cls.temp.name)/'cowsay.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
            '-fPIC', '-D__fastcall__=', '-I'+str(ROOT/'user/include'),
            str(ROOT/'user/bin/cowsay.c'), str(ROOT/'tests/fixtures/cowsay_client.c'),
            '-o', str(target)], check=True)
        cls.lib = c.CDLL(str(target))
        cls.lib.udeks_program_main.argtypes = [c.c_uint8, c.POINTER(c.c_char_p)]
        cls.lib.udeks_program_main.restype = c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self): self.lib.test_reset()

    def invoke(self, *args):
        return self.lib.udeks_program_main(len(args), (c.c_char_p*(len(args)+1))(
            *(a.encode() for a in args), None))

    def lines(self):
        return bytes((c.c_uint8*512).in_dll(self.lib, 'cowsay_output'))[
            : c.c_uint.in_dll(self.lib, 'cowsay_output_length').value].decode().split('\n')

    def test_plain_message_matches_the_classic_cow(self):
        self.assertEqual(self.invoke('cowsay', 'hello'), 0)
        lines = self.lines()
        self.assertEqual(lines[:4], [' _______', '< hello >', ' -------', ' \\   ^__^'])
        self.assertEqual(lines[4], '  \\  (oo)\\_______')
        self.assertEqual(lines[5], '     (__)\\       )\\/\\')
        self.assertEqual(lines[6], '         ||----w |')
        self.assertEqual(lines[7], '         ||     ||')
        self.assertEqual(lines[8], '')

    def test_thought_bubble_uses_parentheses_and_face(self):
        self.assertEqual(self.invoke('cowsay', '-t', 'hello'), 0)
        lines = self.lines()
        self.assertEqual(lines[1], '( hello )')
        self.assertEqual(lines[3], ' O   ^__^')
        self.assertEqual(lines[4], '  o  (oo)\\_______')

    def test_eyes_option_changes_the_face(self):
        self.assertEqual(self.invoke('cowsay', '-e', 'x', 'hi'), 0)
        self.assertIn('  \\  (xx)\\_______', self.lines())

    def test_help_and_bad_options(self):
        self.assertEqual(self.invoke('cowsay', '-h'), 0)
        self.assertIn('Usage:', '\n'.join(self.lines()))
        self.setUp()
        self.assertEqual(self.invoke('cowsay', '-e'), 1)
        self.assertIn('eyes', '\n'.join(self.lines()))


if __name__ == '__main__':
    unittest.main()
# SPDX-License-Identifier: GPL-3.0-or-later
"""cowsay renders the classic cow shape with C128 PETSCII glyphs."""
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BACKSLASH = 0xCD
UPARROW = 0x5E
LINE = 0xC0
BAR = 0xC2


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
        raw = bytes((c.c_uint8*512).in_dll(self.lib, 'cowsay_output'))[
            : c.c_uint.in_dll(self.lib, 'cowsay_output_length').value]
        return raw.split(b'\n')

    def test_plain_message_matches_the_classic_cow(self):
        self.assertEqual(self.invoke('cowsay', 'hello'), 0)
        lines = self.lines()
        self.assertEqual(lines[0], b' ' + bytes([LINE])*7)
        self.assertEqual(lines[1], b'< hello >')
        self.assertEqual(lines[2], b' -------')
        self.assertEqual(lines[3], b' ' + bytes([BACKSLASH]) + b'   '
                         + bytes([UPARROW, LINE, LINE, UPARROW]))
        self.assertEqual(lines[4], b'  ' + bytes([BACKSLASH]) + b'  (oo)'
                         + bytes([BACKSLASH]) + bytes([LINE])*7)
        self.assertEqual(lines[5], b'     (' + bytes([LINE, LINE]) + b')'
                         + bytes([BACKSLASH]) + b'       )'
                         + bytes([BACKSLASH]) + b'/' + bytes([BACKSLASH]))
        self.assertEqual(lines[6], b'         ' + bytes([BAR, BAR]) + b'----w '
                         + bytes([BAR]))
        self.assertEqual(lines[7], b'         ' + bytes([BAR, BAR]) + b'     '
                         + bytes([BAR, BAR]))
        self.assertEqual(lines[8], b'')

    def test_thought_bubble_uses_parentheses_and_face(self):
        self.assertEqual(self.invoke('cowsay', '-t', 'hello'), 0)
        lines = self.lines()
        self.assertEqual(lines[1], b'( hello )')
        self.assertEqual(lines[3], b' O   ' + bytes([UPARROW, LINE, LINE, UPARROW]))
        self.assertEqual(lines[4][:6], b'  o  (')

    def test_eyes_option_changes_the_face(self):
        self.assertEqual(self.invoke('cowsay', '-e', 'x', 'hi'), 0)
        self.assertTrue(any(
            b'  ' + bytes([BACKSLASH]) + b'  (xx)' + bytes([BACKSLASH]) in line
            for line in self.lines()))

    def test_help_and_bad_options(self):
        self.assertEqual(self.invoke('cowsay', '-h'), 0)
        self.assertIn(b'Usage:', b'\n'.join(self.lines()))
        self.setUp()
        self.assertEqual(self.invoke('cowsay', '-e'), 1)
        self.assertIn(b'eyes', b'\n'.join(self.lines()))

    def test_console_maps_petscii_graphics_to_screen_codes(self):
        """The C128 font has no ASCII backslash/underscore; the console must
        map the PETSCII graphics ($C0-$DF) to their screen codes for the cow."""
        text = (ROOT/'src/services/console/vdc_console.c').read_text()
        body = text.split('static unsigned char screen_code')[1].split('\n}')[0]
        self.assertIn('0xC0u', body)
        self.assertIn('0x80u', body)


if __name__ == '__main__':
    unittest.main()
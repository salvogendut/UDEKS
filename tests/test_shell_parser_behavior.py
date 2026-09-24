# SPDX-License-Identifier: GPL-3.0-or-later

import ctypes
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CC = shutil.which("cc")


@unittest.skipUnless(CC, "host C compiler is unavailable")
class ShellParserBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        library = Path(cls.temporary.name) / "shell_parser.so"
        subprocess.run(
            [
                CC,
                "-std=c99",
                "-shared",
                "-fPIC",
                "-I",
                str(ROOT / "include"),
                str(ROOT / "src/services/shell/parser.c"),
                "-o",
                str(library),
            ],
            check=True,
            capture_output=True,
        )
        cls.parser = ctypes.CDLL(str(library)).udeks_shell_tokenize
        cls.parser.argtypes = [
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ubyte,
        ]
        cls.parser.restype = ctypes.c_ubyte

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def tokenize(self, text, capacity=8):
        data = (ctypes.c_ubyte * (len(text) + 1))(*text, 0)
        offsets = (ctypes.c_ubyte * capacity)()
        count = self.parser(data, offsets, capacity)
        if count == 0xFF:
            return count, []
        raw = bytes(data)
        tokens = [raw[offset:].split(b"\0", 1)[0] for offset in offsets[:count]]
        return count, tokens

    def test_splits_bounded_space_and_tab_separated_arguments(self):
        count, tokens = self.tokenize(b"  echo  Mixed\tcase  ")
        self.assertEqual(count, 3)
        self.assertEqual(tokens, [b"echo", b"Mixed", b"case"])

    def test_empty_input_has_no_command(self):
        self.assertEqual(self.tokenize(b" \t "), (0, []))

    def test_reports_argument_capacity_without_overrunning_offsets(self):
        count, tokens = self.tokenize(b"one two three", capacity=2)
        self.assertEqual(count, 0xFF)
        self.assertEqual(tokens, [])


if __name__ == "__main__":
    unittest.main()

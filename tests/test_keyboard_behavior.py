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
class KeyboardBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        temporary = Path(cls.temporary.name)
        stub = temporary / "keyboard_stub.c"
        stub.write_text(
            "unsigned char udeks_keyboard_matrix[11];\n"
            "unsigned char udeks_keyboard_caps;\n"
            "unsigned char udeks_keyboard_display_80;\n"
            "void udeks_keyboard_scan(void) {}\n",
            encoding="ascii",
        )
        library = temporary / "keyboard.so"
        subprocess.run(
            [
                CC,
                "-std=c99",
                "-shared",
                "-fPIC",
                "-I",
                str(ROOT / "include"),
                str(ROOT / "src/services/input/keyboard.c"),
                str(stub),
                "-o",
                str(library),
            ],
            check=True,
            capture_output=True,
        )
        cls.keyboard = ctypes.CDLL(str(library))
        cls.keyboard.udeks_keyboard_normalize.argtypes = [
            ctypes.c_ubyte,
            ctypes.c_ubyte,
        ]
        cls.keyboard.udeks_keyboard_normalize.restype = ctypes.c_ubyte

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def normalized(self, scan_code, modifiers=0):
        return self.keyboard.udeks_keyboard_normalize(scan_code, modifiers)

    def test_letters_support_shift_caps_and_control(self):
        self.assertEqual(self.normalized(10), ord("a"))
        self.assertEqual(self.normalized(10, 0x01), ord("A"))
        self.assertEqual(self.normalized(10, 0x10), ord("A"))
        self.assertEqual(self.normalized(10, 0x11), ord("a"))
        self.assertEqual(self.normalized(10, 0x02), 1)

    def test_digits_and_punctuation_use_ascii_shift_pairs(self):
        self.assertEqual(self.normalized(56), ord("1"))
        self.assertEqual(self.normalized(56, 0x01), ord("!"))
        self.assertEqual(self.normalized(44, 0x01), ord(">"))
        self.assertEqual(self.normalized(55, 0x01), ord("?"))

    def test_c128_extended_text_keys_are_normalized(self):
        self.assertEqual(self.normalized(67), ord("\t"))
        self.assertEqual(self.normalized(72), 0x1B)
        self.assertEqual(self.normalized(76), ord("\n"))
        self.assertEqual(self.normalized(65), ord("8"))

    def test_non_text_and_invalid_keys_return_zero(self):
        self.assertEqual(self.normalized(2), 0)
        self.assertEqual(self.normalized(64), 0)
        self.assertEqual(self.normalized(88), 0)


if __name__ == "__main__":
    unittest.main()

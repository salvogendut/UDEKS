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
class RootConsoleBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        library = Path(cls.temporary.name) / "root_console.so"
        subprocess.run(
            [
                CC,
                "-std=c99",
                "-shared",
                "-fPIC",
                "-I",
                str(ROOT / "include"),
                str(ROOT / "src/services/window/root_console.c"),
                "-o",
                str(library),
            ],
            check=True,
            capture_output=True,
        )
        cls.console = ctypes.CDLL(str(library))
        cls.console.udeks_root_console_row.argtypes = [ctypes.c_ubyte]
        cls.console.udeks_root_console_row.restype = ctypes.POINTER(
            ctypes.c_ubyte
        )
        cls.console.udeks_root_console_write.argtypes = [ctypes.c_ubyte]
        cls.console.udeks_root_console_write_string.argtypes = [ctypes.c_char_p]
        cls.console.udeks_root_console_set_cursor.argtypes = [
            ctypes.c_ubyte,
            ctypes.c_ubyte,
            ctypes.c_ubyte,
        ]
        cls.console.udeks_root_console_row_dirty.argtypes = [ctypes.c_ubyte]
        cls.console.udeks_root_console_row_dirty.restype = ctypes.c_ubyte
        cls.console.udeks_root_console_mark_row_clean.argtypes = [
            ctypes.c_ubyte
        ]
        cls.console.udeks_root_console_cursor_column.restype = ctypes.c_ubyte
        cls.console.udeks_root_console_cursor_row.restype = ctypes.c_ubyte

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.console.udeks_root_console_reset()

    def row(self, number):
        pointer = self.console.udeks_root_console_row(number)
        return bytes(pointer[index] for index in range(64))

    def test_stream_output_and_control_characters(self):
        self.console.udeks_root_console_write_string(b"AB\bC\rD\nE\tF")
        self.assertEqual(self.row(0)[:2], b"DC")
        self.assertEqual(self.row(1)[:9], b"E       F")
        self.assertEqual(self.console.udeks_root_console_cursor_column(), 9)
        self.assertEqual(self.console.udeks_root_console_cursor_row(), 1)

    def test_right_edge_wraps_to_next_row(self):
        self.console.udeks_root_console_write_string(b"X" * 64)
        self.assertEqual(self.row(0), b"X" * 64)
        self.assertEqual(self.console.udeks_root_console_cursor_column(), 0)
        self.assertEqual(self.console.udeks_root_console_cursor_row(), 1)

    def test_bottom_line_scrolls_and_preserves_new_output(self):
        self.console.udeks_root_console_set_cursor(0, 20, 1)
        self.console.udeks_root_console_write_string(b"LAST\nNEXT")
        self.assertEqual(self.row(19)[:4], b"LAST")
        self.assertEqual(self.row(20)[:4], b"NEXT")
        self.assertEqual(self.console.udeks_root_console_cursor_row(), 20)

    def test_damage_tracks_text_and_both_cursor_rows(self):
        self.console.udeks_root_console_mark_all_clean()
        self.console.udeks_root_console_write(ord("A"))
        self.assertEqual(self.console.udeks_root_console_row_dirty(0), 1)
        self.console.udeks_root_console_mark_row_clean(0)
        self.assertEqual(self.console.udeks_root_console_row_dirty(0), 0)

        self.console.udeks_root_console_set_cursor(2, 3, 1)
        self.console.udeks_root_console_mark_all_clean()
        self.console.udeks_root_console_set_cursor(4, 4, 1)
        self.assertEqual(self.console.udeks_root_console_row_dirty(3), 1)
        self.assertEqual(self.console.udeks_root_console_row_dirty(4), 1)

    def test_form_feed_clears_and_homes_console(self):
        self.console.udeks_root_console_write_string(b"TEXT\f")
        self.assertEqual(self.row(0), b" " * 64)
        self.assertEqual(self.console.udeks_root_console_cursor_column(), 0)
        self.assertEqual(self.console.udeks_root_console_cursor_row(), 0)
        for row in range(21):
            self.assertEqual(self.console.udeks_root_console_row_dirty(row), 1)


if __name__ == "__main__":
    unittest.main()

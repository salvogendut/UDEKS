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
        cls.console.udeks_root_console_dirty_span.argtypes = [
            ctypes.c_ubyte,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_ubyte),
        ]
        cls.console.udeks_root_console_dirty_span.restype = ctypes.c_ubyte
        cls.console.udeks_root_console_mark_row_clean.argtypes = [
            ctypes.c_ubyte
        ]
        cls.console.udeks_root_console_cursor_column.restype = ctypes.c_ubyte
        cls.console.udeks_root_console_cursor_row.restype = ctypes.c_ubyte
        cls.console.udeks_root_console_output_begin.argtypes = [ctypes.c_ubyte]
        cls.console.udeks_root_console_output_begin.restype = ctypes.c_ubyte

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.console.udeks_root_console_reset()

    def row(self, number):
        pointer = self.console.udeks_root_console_row(number)
        return bytes(pointer[index] for index in range(64))

    def dirty_span(self, row):
        first = ctypes.c_ubyte()
        last = ctypes.c_ubyte()
        present = self.console.udeks_root_console_dirty_span(
            row, ctypes.byref(first), ctypes.byref(last)
        )
        return present, first.value, last.value

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

    def test_damage_span_tracks_only_changed_cells_and_cursor(self):
        self.console.udeks_root_console_mark_all_clean()
        self.console.udeks_root_console_set_cursor(9, 20, 1)
        self.console.udeks_root_console_mark_all_clean()
        self.console.udeks_root_console_write(ord("A"))
        self.assertEqual(self.dirty_span(20), (1, 9, 10))

    def test_form_feed_clears_and_homes_console(self):
        self.console.udeks_root_console_write_string(b"TEXT\f")
        self.assertEqual(self.row(0), b" " * 64)
        self.assertEqual(self.console.udeks_root_console_cursor_column(), 0)
        self.assertEqual(self.console.udeks_root_console_cursor_row(), 0)
        for row in range(21):
            self.assertEqual(self.console.udeks_root_console_row_dirty(row), 1)

    def background(self, row, column, data):
        row = self.console.udeks_root_console_output_begin(row)
        for ch in data:
            self.console.udeks_root_console_write(ch)
        self.console.udeks_root_console_output_end()
        self.console.udeks_root_console_set_cursor(column, row, 1)
        return row

    def test_output_preserves_editor_at_every_row_and_cursor(self):
        text=b'UDEKS:~> echo draft'
        draft=text.ljust(64,b' ')
        for row in range(21):
            for column in range(8,19):
                self.console.udeks_root_console_reset()
                self.console.udeks_root_console_set_cursor(0,row,0)
                self.console.udeks_root_console_write_string(text)
                self.console.udeks_root_console_set_cursor(column,row,1)
                editor=self.background(row,column,b'A'*130+b'\nB\tC\bD\rE')
                self.assertEqual(self.row(editor),draft,(row,column))
                self.assertEqual(self.console.udeks_root_console_cursor_row(),editor)
                self.assertEqual(self.console.udeks_root_console_cursor_column(),column)
                self.assertEqual(self.console.udeks_root_console_cursor_visible(),1)
                for r in range(21):
                    self.assertEqual(self.console.udeks_root_console_row(r)[64],0)

    def test_output_cursor_survives_request_chunks_without_extra_newlines(self):
        self.console.udeks_root_console_set_cursor(0,20,0)
        self.console.udeks_root_console_write_string(b'UDEKS:~> draft')
        row=20
        for part in (b'alpha ', b'beta', b'\n', b'next ', b'line'):
            row=self.background(row,10,part)
        self.assertEqual(self.row(18).rstrip(),b'alpha beta')
        self.assertEqual(self.row(19).rstrip(),b'next line')
        self.assertEqual(self.row(20).rstrip(),b'UDEKS:~> draft')

    def test_formfeed_preserves_prompt_and_only_clears_output_area(self):
        self.console.udeks_root_console_write_string(b'old\n'*20+b'UDEKS:~> draft')
        self.background(20,8,b'background\fclean')
        self.assertEqual(self.row(0).rstrip(),b'clean')
        for row in range(1,20): self.assertEqual(self.row(row),b' '*64)
        self.assertEqual(self.row(20).rstrip(),b'UDEKS:~> draft')

    def test_normal_scrolling_and_new_output_session_resume_after_edit(self):
        self.console.udeks_root_console_set_cursor(0,20,0)
        self.console.udeks_root_console_write_string(b'editor')
        self.background(20,6,b'background')
        self.console.udeks_root_console_write_string(b'\nanswer\nnew prompt')
        self.console.udeks_root_console_output_reset()
        self.background(20,10,b'new output')
        self.assertEqual([self.row(r).rstrip() for r in range(16,21)],
                         [b'background',b'editor',b'answer',b'new output',b'new prompt'])


if __name__ == "__main__":
    unittest.main()

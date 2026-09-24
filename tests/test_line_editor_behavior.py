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
class LineEditorBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        library = Path(cls.temporary.name) / "line_editor.so"
        subprocess.run(
            [
                CC,
                "-std=c99",
                "-shared",
                "-fPIC",
                "-I",
                str(ROOT / "include"),
                str(ROOT / "src/services/terminal/line_editor.c"),
                "-o",
                str(library),
            ],
            check=True,
            capture_output=True,
        )
        cls.editor = ctypes.CDLL(str(library))
        cls.editor.udeks_line_editor_handle.argtypes = [
            ctypes.c_ubyte,
            ctypes.c_ubyte,
            ctypes.c_ubyte,
        ]
        cls.editor.udeks_line_editor_handle.restype = ctypes.c_ubyte
        cls.editor.udeks_line_editor_text.restype = ctypes.POINTER(ctypes.c_ubyte)
        cls.editor.udeks_line_editor_length.restype = ctypes.c_ubyte
        cls.editor.udeks_line_editor_cursor.restype = ctypes.c_ubyte
        cls.editor.udeks_line_editor_submit.restype = ctypes.c_ubyte
        cls.editor.udeks_line_editor_get_line.argtypes = [
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ubyte,
        ]
        cls.editor.udeks_line_editor_get_line.restype = ctypes.c_ubyte
        cls.editor.udeks_line_editor_history_count.restype = ctypes.c_ubyte
        cls.editor.udeks_line_editor_history_position.restype = ctypes.c_ubyte

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.editor.udeks_line_editor_initialize()

    def handle(self, scan_code=10, character=0, modifiers=0):
        return self.editor.udeks_line_editor_handle(
            scan_code, character, modifiers
        )

    def text(self):
        length = self.editor.udeks_line_editor_length()
        pointer = self.editor.udeks_line_editor_text()
        return bytes(pointer[index] for index in range(length))

    def enter(self, text):
        for character in text:
            self.handle(character=character)
        self.editor.udeks_line_editor_submit()

    def test_inserts_at_cursor_and_backspace_closes_gap(self):
        self.handle(character=ord("a"))
        self.handle(character=ord("c"))
        self.handle(scan_code=2, modifiers=1)
        self.handle(character=ord("b"))
        self.assertEqual(self.text(), b"abc")
        self.assertEqual(self.editor.udeks_line_editor_cursor(), 2)
        self.handle(scan_code=0, character=ord("\b"))
        self.assertEqual(self.text(), b"ac")
        self.assertEqual(self.editor.udeks_line_editor_cursor(), 1)

    def test_home_and_both_cursor_key_forms_are_bounded(self):
        for character in b"abc":
            self.handle(character=character)
        self.handle(scan_code=51)
        self.assertEqual(self.editor.udeks_line_editor_cursor(), 0)
        self.handle(scan_code=86)
        self.handle(scan_code=2)
        self.assertEqual(self.editor.udeks_line_editor_cursor(), 2)
        self.handle(scan_code=85)
        self.assertEqual(self.editor.udeks_line_editor_cursor(), 1)

    def test_capacity_reserves_a_visible_cursor_cell(self):
        for _ in range(60):
            self.handle(character=ord("x"))
        self.assertEqual(self.editor.udeks_line_editor_length(), 54)
        self.assertEqual(self.editor.udeks_line_editor_cursor(), 54)

    def test_submission_is_retained_for_command_dispatch(self):
        for character in b"help":
            self.handle(character=character)
        self.assertEqual(self.editor.udeks_line_editor_submit(), 0)
        self.assertEqual(self.editor.udeks_line_editor_length(), 0)
        self.assertEqual(self.editor.udeks_line_editor_submission_ready(), 1)
        output = (ctypes.c_ubyte * 55)()
        self.assertEqual(self.editor.udeks_line_editor_get_line(output, 55), 0)
        self.assertEqual(bytes(output[:5]), b"help\0")
        self.assertEqual(self.editor.udeks_line_editor_submission_ready(), 0)

    def test_unconsumed_submission_is_explicitly_overwritten(self):
        self.handle(character=ord("a"))
        self.assertEqual(self.editor.udeks_line_editor_submit(), 0)
        self.handle(character=ord("b"))
        self.assertEqual(self.editor.udeks_line_editor_submit(), 1)

    def test_up_and_down_browse_history_and_restore_draft(self):
        self.enter(b"echo one")
        self.enter(b"echo two")
        for character in b"draft":
            self.handle(character=character)

        self.assertEqual(self.handle(scan_code=83), 4)
        self.assertEqual(self.text(), b"echo two")
        self.assertEqual(self.handle(scan_code=83), 4)
        self.assertEqual(self.text(), b"echo one")
        self.assertEqual(self.handle(scan_code=84), 4)
        self.assertEqual(self.text(), b"echo two")
        self.assertEqual(self.handle(scan_code=84), 4)
        self.assertEqual(self.text(), b"draft")
        self.assertEqual(self.editor.udeks_line_editor_history_position(), 0xFF)

    def test_shifted_c128_cursor_down_is_history_up(self):
        self.enter(b"help")
        self.assertEqual(self.handle(scan_code=7, modifiers=1), 4)
        self.assertEqual(self.text(), b"help")
        self.assertEqual(self.handle(scan_code=7), 4)
        self.assertEqual(self.text(), b"")

    def test_history_is_bounded_and_ignores_adjacent_duplicates(self):
        self.enter(b"same")
        self.enter(b"same")
        self.assertEqual(self.editor.udeks_line_editor_history_count(), 1)
        for digit in b"0123456789":
            self.enter(b"cmd" + bytes((digit,)))
        self.assertEqual(self.editor.udeks_line_editor_history_count(), 6)
        for _ in range(6):
            self.assertEqual(self.handle(scan_code=83), 4)
        self.assertEqual(self.text(), b"cmd4")
        self.assertEqual(self.handle(scan_code=83), 0)

    def test_editing_recalled_line_does_not_modify_stored_entry(self):
        self.enter(b"echo")
        self.handle(scan_code=83)
        self.handle(character=ord("!"))
        self.assertEqual(self.text(), b"echo!")
        self.handle(scan_code=83)
        self.assertEqual(self.text(), b"echo")


if __name__ == "__main__":
    unittest.main()

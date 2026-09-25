# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vice_capture import (
    make_basic_wrapper,
    parse_block,
    parse_keybuf,
    parse_monitor_byte,
    quote_monitor_text,
)


class ViceCaptureTests(unittest.TestCase):
    def test_parse_monitor_byte(self):
        reply = b">C:f405  02   .\r\n(C:$29eb) "
        self.assertEqual(parse_monitor_byte(reply, 0xF405), 2)

    def test_parse_monitor_byte_is_case_insensitive(self):
        reply = b">c:F188  80   .\r\n(C:$2800) "
        self.assertEqual(parse_monitor_byte(reply, 0xF188), 0x80)

    def test_parse_monitor_byte_rejects_wrong_address(self):
        with self.assertRaises(ValueError):
            parse_monitor_byte(b">C:f406  02", 0xF405)

    def test_make_basic_wrapper_preserves_payload_address_and_bytes(self):
        source = b"\x00\x20\xaa\xbb\xcc"
        wrapped = make_basic_wrapper(source, 0x2000)
        self.assertEqual(wrapped[:2], b"\x01\x1c")
        payload_offset = 2 + 0x2000 - 0x1C01
        self.assertEqual(wrapped[payload_offset:], source[2:])
        self.assertIn(b"8192", wrapped[:payload_offset])

    def test_make_basic_wrapper_rejects_overlap(self):
        with self.assertRaises(ValueError):
            make_basic_wrapper(b"\x05\x1c\xaa", 0x1C05)

    def test_keybuf_escape_is_safe_for_monitor_command(self):
        text = parse_keybuf(r'xwave\n')
        self.assertEqual(text, "xwave\n")
        self.assertEqual(quote_monitor_text(text), r'"xwave\n"')

    def test_keybuf_quotes_and_backslashes_are_escaped(self):
        self.assertEqual(quote_monitor_text('a"b\\c'), r'"a\"b\\c"')

    def test_ready_block_parser(self):
        self.assertEqual(parse_block("0x1197=65 63 68 6f"),
                         (0x1197, b"echo"))


if __name__ == "__main__":
    unittest.main()

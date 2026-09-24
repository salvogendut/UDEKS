# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class KeyboardSourceTests(unittest.TestCase):
    def test_scanner_covers_cia_and_c128_extended_columns(self):
        source = (ROOT / "src/8502/keyboard_scan.s").read_text(encoding="utf-8")
        self.assertIn("CIA1_PRA                = $dc00", source)
        self.assertIn("CIA1_PRB                = $dc01", source)
        self.assertIn("VIC_KEYBOARD_SELECT     = $d02f", source)
        self.assertIn("_udeks_keyboard_matrix+8", source)
        self.assertIn("cpx #$03", source)
        self.assertIn("saved_ddra", source)
        self.assertIn("saved_ddrb", source)
        self.assertIn("saved_vic_select", source)
        self.assertGreaterEqual(source.count("lda CIA1_PRB"), 4)

    def test_keyboard_is_a_polled_input_service(self):
        descriptor = (ROOT / "src/services/input/descriptor.s").read_text(
            encoding="utf-8"
        )
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        kernel = (ROOT / "src/8502/kernel.c").read_text(encoding="utf-8")
        self.assertIn(".addr _udeks_keyboard_poll", descriptor)
        self.assertIn(".byte $05, $00", descriptor)
        self.assertIn("_udeks_keyboard_service_descriptor", table)
        self.assertIn("udeks_service_poll_all()", kernel)

    def test_driver_queues_press_and_release_events(self):
        source = (ROOT / "src/services/input/keyboard.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("event_queue[UDEKS_KEYBOARD_QUEUE_CAPACITY]", source)
        self.assertIn("UDEKS_KEY_EVENT_PRESS", source)
        self.assertIn("UDEKS_KEY_EVENT_RELEASE", source)
        self.assertIn("previous_matrix", source)
        self.assertIn("candidate_matrix", source)
        self.assertIn(
            "udeks_keyboard_matrix[scan_line] != candidate_matrix[scan_line]",
            source,
        )
        self.assertIn("KEYBOARD_FLAG_DEBOUNCED", source)
        self.assertGreaterEqual(
            source.count("udeks_pointer_keyboard_allowed()"), 2
        )
        self.assertGreaterEqual(source.count("udeks_keyboard_scan();"), 3)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RootTerminalSourceTests(unittest.TestCase):
    def test_service_follows_keyboard_and_owns_no_vdc_registers(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        source = (ROOT / "src/services/terminal/root_terminal.c").read_text(
            encoding="utf-8"
        )
        keyboard = table.index(".addr _udeks_keyboard_service_descriptor")
        terminal = table.index(".addr _udeks_root_terminal_service_descriptor")
        self.assertLess(keyboard, terminal)
        self.assertNotIn("0xd600", source.lower())
        self.assertNotIn("0xd601", source.lower())
        self.assertIn("udeks_console_refresh_root()", source)
        self.assertNotIn("udeks_framebuffer_", source)

    def test_service_routes_press_events_into_bounded_editor(self):
        source = (ROOT / "src/services/terminal/root_terminal.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("udeks_keyboard_event_get(&event)", source)
        self.assertIn("event.type != UDEKS_KEY_EVENT_PRESS", source)
        self.assertIn("udeks_line_editor_handle(", source)
        self.assertIn("udeks_line_editor_submit()", source)
        self.assertIn("INPUT_FIELD_WIDTH           55u", source)
        self.assertIn("render_editor_range", source)
        self.assertIn("udeks_root_console_put(", source)

    def test_descriptor_is_a_polled_terminal_service(self):
        descriptor = (ROOT / "src/services/terminal/descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertIn(".byte $06, $00", descriptor)
        self.assertIn(".addr _udeks_root_terminal_start", descriptor)
        self.assertIn(".addr _udeks_root_terminal_poll", descriptor)

    def test_terminal_accepts_initial_input_and_shell_rearms_later_prompts(self):
        source = (ROOT / "src/services/terminal/root_terminal.c").read_text(
            encoding="utf-8"
        )
        start = source.split("unsigned char udeks_root_terminal_start(void)", 1)[1]
        start = start.split("unsigned char udeks_root_terminal_poll(void)", 1)[0]
        refresh = source.split("static unsigned char refresh_display(void)", 1)[1]
        refresh = refresh.split("unsigned char udeks_root_terminal_start(void)", 1)[0]
        self.assertIn("accepting_input = 1;", start)
        self.assertNotIn("accepting_input = 1;", refresh)
        self.assertIn("accepting_input = 0;", source)
        self.assertIn("unsigned char udeks_root_terminal_prompt(void)", source)


if __name__ == "__main__":
    unittest.main()

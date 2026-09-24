# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ShellSourceTests(unittest.TestCase):
    def test_shell_follows_terminal_in_service_poll_order(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        terminal = table.index(".addr _udeks_root_terminal_service_descriptor")
        shell = table.index(".addr _udeks_shell_service_descriptor")
        self.assertLess(terminal, shell)
        self.assertIn(".byte $0b", table)

    def test_shell_uses_registry_dispatch_and_rearms_terminal_prompt(self):
        source = (ROOT / "src/services/shell/shell.c").read_text(encoding="utf-8")
        self.assertIn("static const struct shell_command commands[]", source)
        self.assertIn("udeks_line_editor_get_line(", source)
        self.assertIn("udeks_root_terminal_prompt()", source)
        for command in (
            "help",
            "clear",
            "echo",
            "uname",
            "lshw",
            "lsmod",
            "lscpu",
            "z80ctl",
            "xinit",
            "xclock",
        ):
            self.assertIn(f'*)"{command}"', source)
        self.assertIn("unsigned char count, unsigned char **arguments", source)
        self.assertIn("UDEKS_STDOUT", source)
        self.assertIn("UDEKS_STDERR", source)
        self.assertIn("udeks_z80_submit", source)
        self.assertIn("udeks_vic_graphics_initialize", source)
        self.assertIn("udeks_vic_graphics_shutdown", source)
        self.assertIn("udeks_xclock_start", source)
        self.assertIn("udeks_xclock_stop", source)
        self.assertIn('*)"-q"', source)

    def test_shell_is_a_resident_polled_service(self):
        descriptor = (ROOT / "src/services/shell/descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertIn(".byte $07, $00", descriptor)
        self.assertIn(".addr _udeks_shell_start", descriptor)
        self.assertIn(".addr _udeks_shell_poll", descriptor)


if __name__ == "__main__":
    unittest.main()

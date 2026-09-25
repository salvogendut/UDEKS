# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ShellSourceTests(unittest.TestCase):
    def test_init_follows_terminal_in_service_poll_order(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        terminal = table.index(".addr _udeks_root_terminal_service_descriptor")
        init = table.index(".addr _udeks_init_service_descriptor")
        self.assertLess(terminal, init)
        self.assertIn(".byte $0c", table)

    def test_init_owns_the_transitional_root_shell_session(self):
        descriptor = (ROOT / "src/services/init/descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertIn(".byte $0b, $00", descriptor)
        self.assertIn("jmp _udeks_shell_start", descriptor)
        self.assertIn("jmp _udeks_shell_poll", descriptor)

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
            "xwave",
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
        self.assertIn("udeks_xwave_start", source)
        self.assertIn("udeks_xwave_stop", source)
        self.assertIn("launch_background", source)
        self.assertIn("publish_background_jobs", source)
        self.assertIn('*)"&"', source)
        self.assertIn("foreground_job", source)
        self.assertIn("udeks_shell_interrupt_foreground", source)
        self.assertIn('*)"-q"', source)

    def test_external_commands_use_generic_bootfs_loader(self):
        source = (ROOT / "src/services/shell/shell.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("UDEKS_TASK_LOADER_ENTRY", source)
        self.assertIn("UDEKS_TASK_NOT_FOUND", source)
        self.assertIn('*)": task slot busy"', source)
        self.assertIn('*)"Unknown command: "', source)
        self.assertNotIn("command_cowsay", source)

    def test_legacy_shell_descriptor_is_not_in_the_boot_table(self):
        descriptor = (ROOT / "src/services/shell/descriptor.s").read_text(
            encoding="utf-8"
        )
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        self.assertIn(".byte $07, $00", descriptor)
        self.assertIn(".addr _udeks_shell_start", descriptor)
        self.assertIn(".addr _udeks_shell_poll", descriptor)
        self.assertNotIn("_udeks_shell_service_descriptor", table)


if __name__ == "__main__":
    unittest.main()

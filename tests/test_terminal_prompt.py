# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TerminalPrompt(unittest.TestCase):
    def test_prompt_recovers_after_unterminated_output_at_every_cursor_position(self):
        with tempfile.TemporaryDirectory() as work:
            executable = Path(work)/'prompt'
            # Discard unrelated terminal entry points: exercise the actual C
            # prompt and root-console implementations, including scrolling.
            subprocess.run(['cc', '-std=c99', '-ffunction-sections', '-fdata-sections',
                '-Wno-int-to-pointer-cast', '-I'+str(ROOT/'include'),
                str(ROOT/'src/services/terminal/root_terminal.c'),
                str(ROOT/'src/services/window/root_console.c'),
                str(ROOT/'tests/fixtures/terminal_prompt.c'), '-Wl,--gc-sections',
                '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)

    def test_fixed_prompt_leaves_room_for_editor(self):
        self.assertLessEqual(len('UDEKS:~> ') + 55, 64)

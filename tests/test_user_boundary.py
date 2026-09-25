# SPDX-License-Identifier: GPL-3.0-or-later

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UserBoundaryTests(unittest.TestCase):
    def test_cowsay_implementation_is_not_resident(self):
        source = (ROOT / "user/bin/cowsay.c").read_text()
        shell = (ROOT / "src/services/shell/shell.c").read_text()
        makefile = (ROOT / "Makefile").read_text()

        self.assertIn('#include "udeks/program.h"', source)
        self.assertIn("udeks_program_main", source)
        self.assertIn("UDEKS_TASK_LOADER_ENTRY", shell)
        self.assertNotIn("udeks_program_main", shell)
        self.assertNotIn("draw_cow", shell)
        self.assertNotIn('*)"cowsay"', shell)

        resident_rules = makefile.split("check:", 1)[0]
        self.assertNotRegex(
            resident_rules,
            re.compile(r"BUILD_8502[^\n]*cowsay|KERNEL_[^\n]*cowsay", re.I),
        )
        self.assertIn("user-sources: $(USER_COWSAY_ASM)", makefile)
        self.assertIn("user-programs: $(USER_BOOTFS)", makefile)
        self.assertIn("--entry cowsay=$(USER_COWSAY_UDEX)", makefile)

    def test_cowsay_has_no_hosted_runtime_dependency(self):
        source = (ROOT / "user/bin/cowsay.c").read_text()
        for forbidden in (
            "<stdio.h>",
            "<stdlib.h>",
            "strcpy(",
            "printf(",
            "exit(",
        ):
            self.assertNotIn(forbidden, source)

    def test_minimal_ush_is_a_separate_persistent_user_image(self):
        source = (ROOT / "user/bin/ush.c").read_text()
        makefile = (ROOT / "Makefile").read_text()
        config = (ROOT / "cfg/8502-user-bank1.cfg").read_text().lower()
        init = (ROOT / "src/services/init/descriptor.s").read_text().lower()

        self.assertIn("udeks_ush_poll", source)
        self.assertIn("udeks_read(UDEKS_STDIN", source)
        self.assertIn("udeks_exec_line", source)
        self.assertIn("udeks_wait_foreground", source)
        self.assertIn("udeks_prompt", source)
        self.assertIn("USH_STATE = UDEKS_USH_STATE_READY", source)
        for command in ('*)"cd"', '*)"echo"', '*)"help"', '*)"pwd"', '*)"uname"'):
            self.assertIn(command, source)
        self.assertIn("CWD_KIND = CWD_ROOT", source)
        self.assertIn('CWD_KIND == CWD_BIN ? "/bin" : "/"', source)
        self.assertIn("--entry ush=$(USER_USH_UDEX)", makefile)
        self.assertIn("--flags 0x01", makefile)
        self.assertIn("app: start = $9000", config)
        self.assertIn("jsr task_bank_reset", init)
        self.assertIn("jsr task_bank_poll", init)
        self.assertIn("jsr persistent_load", init)
        self.assertIn('.byte "ush", $00', init)
        self.assertIn("sta ush_state", init)
        self.assertNotRegex(
            makefile.split("check:", 1)[0],
            re.compile(r"BUILD_8502[^\n]*ush|KERNEL_[^\n]*ush", re.I),
        )

    def test_task_loader_preserves_resident_cc65_zero_page(self):
        loader = (ROOT / "src/boot/stage1-gateway.s").read_text()

        self.assertIn("task_save_zp:", loader)
        self.assertIn("task_restore_zp:", loader)
        self.assertIn("task_saved_zp:          .res $1e", loader)

    def test_transient_filesystem_calls_do_not_use_bank1_gateway(self):
        source = (ROOT / "user/lib/filesystem.c").read_text()

        self.assertIn("UDEKS_SYSCALL_TASK_REQUEST", source)
        self.assertNotIn("UDEKS_TASK_BANK_REQUEST", source)

    def test_architecture_decision_defines_both_sides(self):
        decision = (
            ROOT / "docs/decisions/0007-resident-core-and-loadable-services.md"
        ).read_text()
        for required in (
            "Only mechanisms that must remain authoritative",
            "Everything else is outside the kernel",
            "User executables",
            "bootfs",
        ):
            self.assertIn(required, decision)


if __name__ == "__main__":
    unittest.main()

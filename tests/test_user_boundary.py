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

    def test_task_loader_preserves_resident_cc65_zero_page(self):
        loader = (ROOT / "src/boot/stage1-gateway.s").read_text()

        self.assertIn("task_save_zp:", loader)
        self.assertIn("task_restore_zp:", loader)
        self.assertIn("task_saved_zp:          .res $1e", loader)

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

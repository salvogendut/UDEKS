# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SyscallAbiTests(unittest.TestCase):
    def test_kernel_gate_has_fixed_page_and_vectors(self):
        config = (ROOT / "cfg/8502-bootstrap.cfg").read_text()
        gate = (ROOT / "src/8502/syscall_gate.s").read_text().lower()

        self.assertIn("fill = yes", config)
        self.assertIn('SYSCALLS: load = KERNEL, type = ro, start = $CF00', config)
        self.assertIn("_udeks_syscall_table = $cf00", gate)
        self.assertIn("_udeks_syscall_write_byte_gate = $cf10", gate)
        self.assertIn("_udeks_syscall_write_gate = $cf20", gate)
        self.assertIn("_udeks_syscall_task_request_gate = $cf30", gate)

    def test_public_constants_match_user_veneers(self):
        header = (ROOT / "include/udeks/syscall.h").read_text().lower()
        veneer = (ROOT / "user/lib/syscall.s").read_text().lower()

        self.assertIn("udeks_syscall_write_byte        0xcf10u", header)
        self.assertIn("udeks_syscall_write             0xcf20u", header)
        self.assertIn("udeks_syscall_task_request      0xcf30u", header)
        self.assertIn("udeks_syscall_write_byte = $cf10", veneer)
        self.assertIn("udeks_syscall_write      = $cf20", veneer)
        self.assertNotIn("_udeks_stream_", veneer)

    def test_user_entry_marshals_register_abi(self):
        entry = (ROOT / "user/lib/entry.s").read_text().lower()

        for instruction in ("sta tmp1", "stx ptr1", "sty ptr1+1", "jsr pusha"):
            self.assertIn(instruction, entry)
        self.assertIn("jmp _udeks_program_main", entry)
        self.assertIn("_udeks_program_entry = $0200", entry)

    def test_task_loader_accepts_current_syscall_minor(self):
        loader = (ROOT / "src/boot/stage1-gateway.s").read_text().lower()
        check = loader.split("task_check_syscalls:", 1)[1].split(
            "task_find_file:", 1
        )[0]

        self.assertIn("lda syscall_table+5", check)
        self.assertIn("cmp #$03", check)
        self.assertIn("bcs task_bad_syscalls", check)

    def test_user_link_is_separate_from_kernel(self):
        makefile = (ROOT / "Makefile").read_text()
        user_rule = makefile.split("$(USER_COWSAY_BIN):", 1)[1].split("\n\n", 1)[0]
        kernel_rule = makefile.split("$(KERNEL_BIN):", 1)[1].split(
            "$(PANIC_PROBE_KERNEL_BIN):", 1
        )[0]

        self.assertIn("cfg/8502-user-app1.cfg", user_rule)
        self.assertIn("$(USER_SYSCALL_OBJ)", user_rule)
        self.assertNotIn("USER_COWSAY", kernel_rule)


if __name__ == "__main__":
    unittest.main()

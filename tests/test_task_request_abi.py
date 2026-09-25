# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TaskRequestAbiTests(unittest.TestCase):
    def test_common_record_is_bounded_before_vic_outline_state(self):
        header = (ROOT / "include/udeks/task_request.h").read_text().lower()

        self.assertIn("udeks_task_request_base          0xf359u", header)
        self.assertIn("udeks_task_request_size          38u", header)
        self.assertIn("udeks_task_request_payload_size  24u", header)
        self.assertIn("udeks_task_command_base          0xf3a0u", header)
        self.assertIn("udeks_task_command_size          55u", header)
        self.assertIn("udeks_treq_payload               14u", header)

    def test_dispatcher_uses_fixed_resident_and_common_vectors(self):
        syscalls = (ROOT / "src/8502/syscall_gate.s").read_text().lower()
        task_gate = (ROOT / "src/8502/task_bank_gateway.s").read_text().lower()

        self.assertIn("task_request_dispatch   = $cf30", task_gate)
        self.assertIn("_udeks_task_bank_request_gate:", task_gate)
        self.assertIn("jsr task_request_dispatch", task_gate)
        self.assertIn("_udeks_syscall_task_request_gate = $cf30", syscalls)
        self.assertIn(".assert * <= $d000", syscalls)
        self.assertIn('.segment "taskrequest"', syscalls)

    def test_initial_operations_follow_unix_descriptor_and_errno_values(self):
        header = (ROOT / "include/udeks/task_request.h").read_text().lower()
        dispatcher = (ROOT / "src/8502/syscall_gate.s").read_text().lower()

        for value in ("ebadf                 9u", "eagain                11u",
                      "einval                22u", "enosys                38u",
                      "eproto                71u"):
            self.assertIn(value, header)
        self.assertIn("jsr _udeks_line_editor_read", dispatcher)
        self.assertIn("jsr _udeks_root_console_write", dispatcher)
        self.assertIn("jsr _udeks_shell_dispatch_line", dispatcher)
        self.assertIn("jsr _udeks_root_terminal_prompt", dispatcher)

    def test_task_stream_wrapper_has_no_resident_private_imports(self):
        wrapper = (ROOT / "user/lib/task_stream.c").read_text().lower()
        program = (ROOT / "user/include/udeks/program.h").read_text().lower()

        self.assertIn("udeks_task_bank_request", wrapper)
        self.assertIn("udeks_treq_op_read", wrapper)
        self.assertIn("udeks_treq_op_write", wrapper)
        self.assertIn("udeks_treq_op_exec", wrapper)
        self.assertIn("udeks_treq_op_wait", wrapper)
        self.assertIn("udeks_treq_op_prompt", wrapper)
        self.assertNotIn("udeks_root_console", wrapper)
        self.assertNotIn("udeks_line_editor", wrapper)
        self.assertIn("extern unsigned char udeks_errno", program)

    def test_line_reader_is_a_compact_separate_assembly_module(self):
        reader = (ROOT / "src/8502/line_editor_read.s").read_text().lower()
        editor = (ROOT / "src/services/terminal/line_editor.c").read_text().lower()

        self.assertIn("_udeks_line_editor_read:", reader)
        self.assertIn("jsr popax", reader)
        self.assertIn("lda #$0a", reader)
        self.assertIn("udeks_line_editor_submitted_text", editor)
        self.assertNotIn("unsigned char udeks_line_editor_read(", editor)


if __name__ == "__main__":
    unittest.main()

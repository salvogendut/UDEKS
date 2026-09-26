# SPDX-License-Identifier: GPL-3.0-or-later

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TaskRequestAbiTests(unittest.TestCase):
    @staticmethod
    def defines(name: str) -> dict[str, int]:
        text = (ROOT / name).read_text(encoding="utf-8")
        values = {}
        for match in re.finditer(
            r"^#define\s+(UDEKS_[A-Z0-9_]+)\s+(0x[0-9A-Fa-f]+|\d+)(?:u)?$",
            text,
            re.MULTILINE,
        ):
            values[match.group(1)] = int(match.group(2), 0)
        return values

    def test_lifecycle_operations_and_layouts_are_frozen(self):
        values = self.defines("include/udeks/task_request.h")

        self.assertEqual(values["UDEKS_TASK_REQUEST_ABI_MINOR"], 3)
        # 0.2 operation numbers and behavior are preserved.
        self.assertEqual(values["UDEKS_TREQ_OP_READ"], 1)
        self.assertEqual(values["UDEKS_TREQ_OP_WRITE"], 2)
        self.assertEqual(values["UDEKS_TREQ_OP_EXEC"], 3)
        self.assertEqual(values["UDEKS_TREQ_OP_WAIT"], 4)
        self.assertEqual(values["UDEKS_TREQ_OP_PROMPT"], 5)
        self.assertEqual(values["UDEKS_TREQ_OP_OPEN"], 6)
        self.assertEqual(values["UDEKS_TREQ_OP_CLOSE"], 9)
        # 0.3 lifecycle operations use new numbers.
        self.assertEqual(values["UDEKS_TREQ_OP_YIELD"], 10)
        self.assertEqual(values["UDEKS_TREQ_OP_EXIT"], 11)
        self.assertEqual(values["UDEKS_TREQ_OP_WAITPID"], 12)
        self.assertEqual(values["UDEKS_TREQ_OP_SLEEP"], 13)
        self.assertEqual(values["UDEKS_TREQ_OP_CANCEL"], 14)
        self.assertEqual(values["UDEKS_TREQ_OP_SPAWN"], 15)

    def test_lifecycle_flags_payloads_and_counts_are_frozen(self):
        values = self.defines("include/udeks/task_request.h")

        self.assertEqual(values["UDEKS_TREQ_WAITPID_NOHANG"], 0x01)
        self.assertEqual(values["UDEKS_TREQ_TASK_ID_LOW"], 0)
        self.assertEqual(values["UDEKS_TREQ_TASK_ID_HIGH"], 1)
        self.assertEqual(values["UDEKS_TREQ_EXIT_STATUS"], 0)
        self.assertEqual(values["UDEKS_TREQ_WAIT_STATUS"], 2)
        self.assertEqual(values["UDEKS_TREQ_WAIT_RESERVED"], 3)
        self.assertEqual(values["UDEKS_TREQ_CANCEL_STATUS"], 2)
        self.assertEqual(values["UDEKS_TREQ_SLEEP_TICKS_LOW"], 0)
        self.assertEqual(values["UDEKS_TREQ_SLEEP_TICKS_HIGH"], 1)
        self.assertEqual(values["UDEKS_TREQ_SPAWN_NAME_LENGTH"], 0)
        self.assertEqual(values["UDEKS_TREQ_SPAWN_NAME"], 1)
        self.assertEqual(values["UDEKS_TREQ_SPAWN_NAME_MAX"], 16)
        self.assertEqual(values["UDEKS_TREQ_YIELD_COUNT"], 0)
        self.assertEqual(values["UDEKS_TREQ_EXIT_COUNT"], 1)
        self.assertEqual(values["UDEKS_TREQ_WAITPID_COUNT"], 2)
        self.assertEqual(values["UDEKS_TREQ_SLEEP_COUNT"], 2)
        self.assertEqual(values["UDEKS_TREQ_CANCEL_COUNT"], 3)
        self.assertEqual(values["UDEKS_TREQ_SPAWN_COUNT"], 17)
        self.assertEqual(values["UDEKS_TREQ_SLEEP_TICKS_MAX"], 600)
        self.assertEqual(values["UDEKS_TREQ_CANCEL_STATUS_DEFAULT"], 130)
        self.assertEqual(values["UDEKS_TREQ_TASK_ID_MAX"], 8)

    def test_lifecycle_errnos_match_linux_values(self):
        values = self.defines("include/udeks/task_request.h")

        for name, value in (
            ("ESRCH", 3),
            ("ENOEXEC", 8),
            ("ECHILD", 10),
            ("EAGAIN", 11),
            ("ENOMEM", 12),
            ("EBUSY", 16),
            ("EINVAL", 22),
            ("ENOSYS", 38),
            ("EPROTO", 71),
        ):
            self.assertEqual(values[f"UDEKS_TREQ_{name}"], value)

    def test_dispatcher_accepts_03_and_stubs_new_operations(self):
        dispatcher = (ROOT / "src/8502/syscall_gate.s").read_text().lower()
        bootfs = (
            ROOT / "src/services/filesystem/bootfs_request.s"
        ).read_text().lower()

        self.assertIn("cmp #$04", dispatcher)
        self.assertIn("cmp #$0a", dispatcher)
        self.assertIn("task_request_fallback:", dispatcher)
        self.assertIn("jmp _udeks_bootfs_request", dispatcher)
        # The bootfs fallback answers unknown operations with ENOSYS.
        self.assertIn("lda #err_enosys", bootfs)
        self.assertIn("jmp finish_error", bootfs)
        for handler in (
            "task_read:", "task_write:", "task_exec:", "task_wait:",
            "task_prompt:",
        ):
            self.assertIn(handler, dispatcher)

    def test_abi_document_freezes_the_lifecycle_contract(self):
        document = (ROOT / "abi/task-request.md").read_text(encoding="utf-8")

        self.assertIn("ABI 0.3", document)
        self.assertIn("`EXEC` (`3`) is not task creation", document)
        self.assertIn("`SPAWN` (`15`)", document)
        self.assertIn("`NOHANG`", document)
        self.assertIn("ENOSYS", document)
        self.assertIn("1/60", document)
        self.assertIn("`600`", document)
        self.assertIn("`130`", document)
        self.assertIn("`ESRCH`", document)
        self.assertIn("`ECHILD`", document)
        self.assertIn("Rejection is atomic", document)

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
        app_gateway = (ROOT / "src/8502/app_gateway.s").read_text().lower()
        task_gate = (ROOT / "src/8502/task_bank_gateway.s").read_text().lower()

        self.assertIn("task_request_dispatch   = $cf30", task_gate)
        self.assertIn("_udeks_task_bank_request_gate:", task_gate)
        self.assertIn("jsr task_request_dispatch", task_gate)
        self.assertIn("_udeks_syscall_task_request_gate = $cf30", syscalls)
        self.assertIn(".include \"app_gateway.s\"", syscalls)
        self.assertIn(".assert * <= $d000", app_gateway)
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
        self.assertNotIn("jsr _udeks_shell_dispatch_line", dispatcher)
        self.assertIn("sta shell_pending_exec", dispatcher)
        shell = (ROOT / "src/services/shell/shell.c").read_text().lower()
        self.assertIn("status_pending_exec", shell)
        self.assertIn("result = udeks_shell_dispatch_line();", shell)
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

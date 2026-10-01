# SPDX-License-Identifier: GPL-3.0-or-later
import re
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from task_poll_probe import validate_completion
import shadow_boot_probe as sp


class PollResidentTests(unittest.TestCase):
    def text(self, name):
        return (ROOT / name).read_text()

    def test_reference_constants_match_public_contract(self):
        def defines(path):
            return {name: int(value, 0) for name, value in re.findall(
                r"^#define\s+(\w+)\s+(0x[0-9A-Fa-f]+|\d+)u?$",
                self.text(path), re.M)}
        public = defines("include/udeks/task_request.h")
        policy = defines("include/udeks/task_poll_policy.h")
        for reference, actual in (
            ("OPERATION", "UDEKS_TREQ_OP_POLL"),
            ("COUNT", "UDEKS_TREQ_POLL_COUNT"),
            ("READABLE", "UDEKS_TREQ_POLL_READABLE"),
            ("TIMEOUT_MAX", "UDEKS_TREQ_POLL_TIMEOUT_MAX"),
            ("FOREVER", "UDEKS_TREQ_POLL_FOREVER"),
        ):
            self.assertEqual(policy["UDEKS_POLL_POLICY_" + reference], public[actual])
        self.assertEqual(policy["UDEKS_POLL_POLICY_ABI_MINOR"], 4)
        self.assertGreaterEqual(public["UDEKS_TASK_REQUEST_ABI_MINOR"], 4)

    def test_private_helpers_are_address_asserted(self):
        source = self.text("src/scheduler/task_yield_handler.s")
        for label, address in (("task_wait_snapshot_gate", "c909"),
                               ("task_block_caller_gate", "c90c"),
                               ("task_console_get_line_gate", "c90f")):
            self.assertIn(f".assert {label} = ${address}", source)
        self.assertIn(".assert yield_handler_end <= $cdbd", source)

    def test_infinite_registration_skips_deadline_arithmetic(self):
        source = self.text("src/scheduler/task_wait_state.s")
        register = source.split("poll_valid:")[1].split("poll_ready:")[0]
        self.assertLess(register.index("beq poll_block"), register.index("adc TREQ_PAYLOAD+2"))
        self.assertIn("jsr $c909", register)
        self.assertIn("jmp $c90c", register)

    def test_wake_scan_observes_input_before_deadline(self):
        source = self.text("src/scheduler/task_wait_state.s")
        wake = source.split("input_waiting:")[1].split("input_ready:")[0]
        self.assertLess(wake.index("_udeks_line_editor_submitted_ready_value"),
                        wake.index("sbc _udeks_task_wait_selector_private"))
        self.assertNotIn("_udeks_line_editor_read", wake)
        self.assertIn("cpy #TASK_COUNT", source)

    def test_native_owner_suppresses_only_legacy_input_read(self):
        source = self.text("src/scheduler/task_wait_state.s")
        ownership = source.split("_udeks_task_console_get_line:")[1].split(
            "_udeks_task_wait_publish_current:")[0]
        self.assertIn("ldx $f3d9", ownership)
        self.assertIn("jmp _udeks_line_editor_get_line", ownership)
        self.assertIn("jmp incsp2", ownership)
        shell = self.text("src/services/shell/shell.c")
        self.assertIn("udeks_shell_read_line(", shell)
        self.assertIn("if (S(23))", shell)
        self.assertIn("if (foreground)", shell)

    def test_ush_waits_before_reading(self):
        source = self.text("user/bin/ush.c")
        self.assertLess(source.index("udeks_poll(UDEKS_STDIN"),
                        source.index("udeks_read(UDEKS_STDIN"))
        self.assertIn("udeks_wait_foreground()", source)

    def test_compiled_probe_retains_real_stack_locals(self):
        source = self.text("user/probes/task_poll.c")
        self.assertIn("unsigned char guard[16]", source)
        self.assertIn("guard[index] ==", source)
        self.assertIn("REQ[UDEKS_TREQ_SEQUENCE] == sequence", source)
        self.assertIn("task-poll-probe:", self.text("Makefile"))

    def test_complete_record(self):
        validate_completion(b"UPOL\xa5\x00\xa1\x00")

    def test_incomplete_or_failed_records_rejected(self):
        for record in (b"", b"UPOL\x03\x00\xa1\x00",
                       b"UPOL\xa5\x01\xa1\x00", b"UPOL\xa5\x00\xa1\x00X"):
            with self.assertRaises(ValueError):
                validate_completion(record)

    def test_preserved_records_pass_on_both_disk_formats(self):
        raw = ROOT / "bench/results/2026-09-27-event-waits/raw"
        for disk in ("d71", "d64"):
            validate_completion((raw / f"poll-{disk}-complete.bin").read_bytes()[2:])
            self.assertEqual((raw / f"poll-{disk}-cleared-waits.bin").read_bytes()[2:], bytes(8))
            self.assertEqual((raw / f"poll-{disk}-extra-ready.bin").read_bytes()[2:], b"\x01\x01")
            self.assertEqual((raw / f"poll-{disk}-extra-waits.bin").read_bytes()[2:], b"\x02\x02")

    def test_preserved_stopped_waiters_remain_stopped(self):
        raw = ROOT / "bench/results/2026-09-27-event-waits/raw"
        for disk in ("d71", "d64"):
            slots = (raw / f"poll-{disk}-extra-slots.bin").read_bytes()[2:]
            for offset in (0, 8):
                self.assertEqual((slots[offset + 1], slots[offset + 2], slots[offset + 6]), (5, 0, 2))

    def test_kernel_write_rejects_invalid_bounds_before_connecting(self):
        for address, data in ((-1, b"X"), (0xFFFF, b"XY"), (0, b"")):
            with patch.object(sp.socket, "create_connection") as connect:
                with self.assertRaises(ValueError):
                    sp.write_kernel_blocks(1, [(address, data)])
                connect.assert_not_called()

    def test_kernel_write_preserves_map_and_resumes_only_last(self):
        class Connection:
            def __init__(self):
                self.commands = []
                self.replies = [b"(C:$2000) "]  # initial prompt, not a command result

            def __enter__(self): return self
            def __exit__(self, *args): pass
            def settimeout(self, seconds): pass

            def sendall(self, data):
                self.commands.append(data)
                if data.startswith(b"m "):
                    self.replies.append(b">C:ff00 7f\n(C:$2000) ")
                elif data != b"x\n":
                    self.replies.append(b"(C:$2000) ")

            def recv(self, count): return self.replies.pop(0)

        connection = Connection()
        with patch.object(sp.socket, "create_connection", return_value=connection):
            sp.write_kernel_blocks(1, [(0xA000, b"\x01\x02")])
        self.assertEqual(connection.commands, [b"m ff00 ff00\n", b"> ff01 00\n",
                                              b"> a000 01 02\n", b"> ff00 7f\n", b"x\n"])
        connection = Connection()
        payload = bytes(range(256))+b'end'
        with patch.object(sp.socket, "create_connection", return_value=connection):
            sp.write_kernel_blocks(1, [(0x9900, payload)])
        self.assertEqual(connection.commands[:2], [b'm ff00 ff00\n', b'> ff01 00\n'])
        self.assertEqual(connection.commands[-2:], [b'> ff00 7f\n', b'x\n'])
        blocks = connection.commands[2:-2]
        self.assertEqual(len(blocks), 9)
        decoded = bytearray()
        for index, command in enumerate(blocks):
            fields = command.split()
            self.assertEqual(int(fields[1], 16), 0x9900+32*index)
            self.assertLessEqual(len(fields)-2, 32)
            decoded.extend(int(value, 16) for value in fields[2:])
        self.assertEqual(decoded, payload)


if __name__ == "__main__":
    unittest.main()

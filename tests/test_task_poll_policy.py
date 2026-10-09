# SPDX-License-Identifier: GPL-3.0-or-later

import ctypes
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CC = shutil.which("cc")
U8 = ctypes.c_ubyte
UINT = ctypes.c_uint
EPROTO, ENOSYS, ESRCH, EINVAL, EBADF = 71, 38, 3, 22, 9
WAIT, READY, EXPIRED = 0, 1, 2
FOREVER = 0xFFFF


@unittest.skipUnless(CC, "host C compiler is unavailable")
class PollPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        library = Path(cls.temporary.name) / "task_poll_policy.so"
        built = subprocess.run(
            [CC, "-std=c99", "-shared", "-fPIC", "-Wall", "-Wextra", "-Werror",
             "-Wno-unknown-pragmas",  # existing line-editor cc65 BSS pragmas
             "-I", str(ROOT / "include"),
             str(ROOT / "src/kernel/task_state.c"),
             str(ROOT / "src/kernel/task_poll_policy.c"),
             str(ROOT / "src/services/terminal/line_editor.c"),
             "-o", str(library)],
            capture_output=True, text=True,
        )
        if built.returncode != 0:
            raise RuntimeError(built.stderr)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.udeks_poll_policy_validate.argtypes = [
            ctypes.POINTER(U8), U8, ctypes.POINTER(UINT)
        ]
        cls.lib.udeks_poll_policy_validate.restype = U8
        cls.lib.udeks_poll_policy_decide.argtypes = [U8, UINT, UINT, UINT]
        cls.lib.udeks_poll_policy_decide.restype = U8
        cls.lib.udeks_lifecycle_reset.restype = U8
        cls.lib.udeks_lifecycle_create.argtypes = [U8, U8, U8]
        cls.lib.udeks_lifecycle_create.restype = U8
        cls.lib.udeks_lifecycle_apply.argtypes = [U8, U8, U8]
        cls.lib.udeks_lifecycle_apply.restype = U8
        cls.lib.udeks_lifecycle_publish.argtypes = [ctypes.POINTER(U8)]
        cls.lib.udeks_lifecycle_publish.restype = None
        cls.lib.udeks_lifecycle_get.argtypes = [U8]
        cls.lib.udeks_lifecycle_get.restype = U8
        cls.lib.udeks_lifecycle_wait_reason.argtypes = [U8]
        cls.lib.udeks_lifecycle_wait_reason.restype = U8
        cls.lib.udeks_line_editor_handle.argtypes = [U8, U8, U8]
        cls.lib.udeks_line_editor_handle.restype = U8
        cls.lib.udeks_line_editor_submit.restype = U8
        cls.lib.udeks_line_editor_submission_ready.restype = U8

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.assertEqual(self.lib.udeks_lifecycle_reset(), 0)
        self.assertEqual(self.lib.udeks_lifecycle_create(1, 0, 1), 0)
        self.assertEqual(self.lib.udeks_lifecycle_apply(1, 2, 0), 0)  # admit
        self.assertEqual(self.lib.udeks_lifecycle_apply(1, 3, 0), 0)  # dispatch

    def request(self, timeout=600):
        record = (U8 * 38)(*range(38))
        record[:14] = b"UTRQ" + bytes((0, 4, 1, 16, 0x53, 0, 4, 0, 0, 0))
        record[14:18] = bytes((1, 0, timeout & 255, timeout >> 8))
        return record

    def snapshot(self):
        record = (U8 * 16)()
        self.lib.udeks_lifecycle_publish(record)
        slots = (U8 * 64).in_dll(self.lib, "udeks_lifecycle_slots_private")
        return bytes(record), bytes(slots)

    def validate(self, request, expected, caller=1, timeout=None):
        before_record, before_table = bytes(request), self.snapshot()
        decoded = UINT(0xA55A)
        result = self.lib.udeks_poll_policy_validate(
            request, caller, ctypes.byref(decoded)
        )
        self.assertEqual(result, expected)
        self.assertEqual(bytes(request), before_record)
        self.assertEqual(self.snapshot(), before_table)
        self.assertEqual(decoded.value, timeout if expected == 0 else 0xA55A)

    def decide(self, ready, timeout, now, deadline):
        before = self.snapshot()
        result = self.lib.udeks_poll_policy_decide(ready, timeout, now, deadline)
        self.assertEqual(self.snapshot(), before)
        return result

    def test_success_decodes_timeout_and_preserves_request_and_table(self):
        for timeout in (0, 1, 255, 256, 599, 600, FOREVER):
            with self.subTest(timeout=timeout):
                self.validate(self.request(timeout), 0, timeout=timeout)

    def test_poll_accepts_compatible_minors(self):
        for minor in range(4,21):
            request = self.request(FOREVER)
            request[5] = minor
            self.validate(request, 0, timeout=FOREVER)
        for minor in range(4):
            request = self.request()
            request[5] = minor
            request[9] = 255
            self.validate(request, ENOSYS, caller=255)
        for minor in (21, 255):
            request = self.request()
            request[5] = minor
            self.validate(request, EPROTO)

    def test_bad_envelope_precedes_operation_and_caller_checks(self):
        for offset, value in (
            (0, 0), (1, 0), (2, 0), (3, 0), (4, 1),
            (6, 0), (6, 2), (6, 0x80),
        ):
            with self.subTest(offset=offset, value=value):
                request = self.request()
                request[offset] = value
                request[7] = 255
                self.validate(request, EPROTO, caller=255)

    def test_unknown_operation_precedes_caller_descriptor_and_payload(self):
        for operation in (*range(16), 17, 255):
            request = self.request()
            request[7] = operation
            request[9] = 255
            request[10] = 0
            request[13] = 255
            self.validate(request, ENOSYS, caller=255)

    def test_undefined_and_nonrunning_callers_are_rejected(self):
        for caller in (0, 2, 8, 9, 255):
            self.validate(self.request(), ESRCH, caller=caller)
        slots = (U8 * 64).in_dll(self.lib, "udeks_lifecycle_slots_private")
        for state in (1, 2, 4, 5, 6):
            slots[1] = state
            self.validate(self.request(), EINVAL)
        slots[1] = 3
        U8.in_dll(self.lib, "udeks_lifecycle_current_private").value = 2
        self.validate(self.request(), EINVAL)

    def test_only_stdin_is_supported(self):
        for descriptor in range(1, 256):
            request = self.request()
            request[9] = descriptor
            self.validate(request, EBADF)

    def test_flags_and_count_are_exact(self):
        for flags in range(1, 256):
            request = self.request()
            request[13] = flags
            self.validate(request, EINVAL)
        for count in range(256):
            if count != 4:
                request = self.request()
                request[10] = count
                self.validate(request, EINVAL)

    def test_mask_is_full_width_and_only_readable(self):
        for mask in (0, 3, 0x0101, 0x8001, 0xFFFF, *(1 << i for i in range(1, 16))):
            with self.subTest(mask=mask):
                request = self.request()
                request[14] = mask & 255
                request[15] = mask >> 8
                self.validate(request, EINVAL)

    def test_timeout_range_has_no_high_byte_aliases(self):
        for timeout in (601, 1024, 0x8000, 0xFE00, 0xFF00, 0xFF01, 0xFFFE):
            with self.subTest(timeout=timeout):
                self.validate(self.request(timeout), EINVAL)

    def test_readiness_wins_immediate_and_expired_timeouts(self):
        for timeout in (0, 1, 600, FOREVER):
            for now in (99, 100, 101):
                for ready in (1, 255):
                    self.assertEqual(self.decide(ready, timeout, now, 100), READY)

    def test_no_readiness_is_immediate_or_indefinite_as_requested(self):
        for now in (0, 1, 0x7FFF, 0x8000, 0xFFFF):
            self.assertEqual(self.decide(0, 0, now, 100), EXPIRED)
            self.assertEqual(self.decide(0, FOREVER, now, 100), WAIT)

    def test_finite_wait_uses_modular_16_bit_deadlines(self):
        for start in (0, 1, 0x7FFF, 0xFFF0, 0xFFFF):
            for timeout in (1, 600):
                deadline = (start + timeout) & 0xFFFF
                for elapsed in (0, timeout - 1, timeout, timeout + 1, timeout + 300):
                    now = (start + elapsed) & 0xFFFF
                    with self.subTest(start=start, timeout=timeout, elapsed=elapsed):
                        expected = WAIT if elapsed < timeout else EXPIRED
                        self.assertEqual(self.decide(0, timeout, now, deadline), expected)

    def test_readiness_can_change_without_consumption_or_state_mutation(self):
        self.assertEqual(self.decide(0, 600, 30, 630), WAIT)
        self.assertEqual(self.decide(1, 600, 31, 630), READY)
        self.assertEqual(self.decide(1, 600, 31, 630), READY)
        # Another permitted reader can drain the line: notification reserves
        # no bytes, so the next wait may block again.
        self.assertEqual(self.decide(0, 600, 32, 632), WAIT)

    def test_empty_and_nonempty_editor_submissions_remain_readable(self):
        for text in (b"", b"echo hello"):
            self.lib.udeks_line_editor_initialize()
            for byte in text:
                self.lib.udeks_line_editor_handle(10, byte, 0)
            self.assertEqual(self.lib.udeks_line_editor_submit(), 0)
            ready = self.lib.udeks_line_editor_submission_ready()
            submitted = (U8 * 55).in_dll(
                self.lib, "udeks_line_editor_submitted_text"
            )
            before = bytes(submitted)
            for _ in range(2):  # two independent observers
                self.assertEqual(self.decide(ready, FOREVER, 100, 0), READY)
            self.assertEqual(self.lib.udeks_line_editor_submission_ready(), 1)
            self.assertEqual(bytes(submitted), before)

    def test_stopped_input_waiter_can_record_wake_without_running(self):
        self.assertEqual(self.lib.udeks_lifecycle_apply(1, 5, 2), 0)  # block/input
        self.assertEqual(self.lib.udeks_lifecycle_apply(1, 7, 0), 0)  # stop
        self.assertEqual(self.decide(1, FOREVER, 0, 0), READY)
        # The caller, not the pure policy, records the event exactly once.
        self.assertEqual(self.lib.udeks_lifecycle_apply(1, 6, 0), 0)  # unblock
        self.assertEqual(self.lib.udeks_lifecycle_get(1), 5)
        self.assertEqual(self.lib.udeks_lifecycle_wait_reason(1), 0)
        self.assertNotEqual(self.lib.udeks_lifecycle_apply(1, 6, 0), 0)
        self.assertEqual(self.lib.udeks_lifecycle_apply(1, 8, 0), 0)  # continue
        self.assertEqual(self.lib.udeks_lifecycle_get(1), 2)


class PollPolicyBoundaryTests(unittest.TestCase):
    def test_resident_operation_is_advertised(self):
        header = (ROOT / "include/udeks/task_request.h").read_text()
        self.assertRegex(header, r"#define UDEKS_TASK_REQUEST_ABI_MINOR\s+20u")
        self.assertRegex(header, r"#define UDEKS_TREQ_OP_POLL\s+16u")
        source = (ROOT / "src/8502/syscall_gate.s").read_text()
        self.assertIn("lda TREQ_BASE+$05\n        cmp #$15", source)

    def test_policy_is_compile_only_and_does_not_mutate_or_consume(self):
        source = (ROOT / "src/kernel/task_poll_policy.c").read_text()
        for forbidden in (
            "udeks_lifecycle_apply", "udeks_lifecycle_create",
            "udeks_lifecycle_reset", "udeks_line_editor_read",
            "udeks_line_editor_get_line",
        ):
            self.assertNotIn(forbidden, source)
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("task-poll-policy: $(BUILD_8502)/task_poll_policy.o", makefile)
        # Only the compile-only target and the assembly rule may mention this
        # object. A resident link/dependency must not quietly pull it in.
        self.assertEqual(len(re.findall(r"task_poll_policy\.o", makefile)), 2)


if __name__ == "__main__":
    unittest.main()

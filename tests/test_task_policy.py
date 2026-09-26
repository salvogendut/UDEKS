# SPDX-License-Identifier: GPL-3.0-or-later

import ctypes
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CC = shutil.which("cc")

FREE = 0
RUNNABLE = 2
RUNNING = 3
ZOMBIE = 6

ADMIT = 2
DISPATCH = 3
YIELD = 4
EXIT = 9
REAP = 10
FLAG_USER = 0x01

YIELD_OP = 10
EXIT_OP = 11
WAITPID_OP = 12
SLEEP_OP = 13
CANCEL_OP = 14
SPAWN_OP = 15

NOHANG = 0x01

OK = 0
ESRCH = 3
ENOEXEC = 8
ECHILD = 10
EAGAIN = 11
ENOMEM = 12
EBUSY = 16
EINVAL = 22
ENOSYS = 38

PAYLOAD_SIZE = 24


def compile_library(directory: str) -> ctypes.CDLL:
    library = Path(directory) / "task_policy.so"
    subprocess.run(
        [
            CC,
            "-std=c99",
            "-shared",
            "-fPIC",
            "-I",
            str(ROOT / "include"),
            str(ROOT / "src/kernel/task_state.c"),
            str(ROOT / "src/kernel/task_policy.c"),
            "-o",
            str(library),
        ],
        check=True,
        capture_output=True,
    )
    loaded = ctypes.CDLL(str(library))
    loaded.udeks_lifecycle_reset.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_create.argtypes = [
        ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte
    ]
    loaded.udeks_lifecycle_create.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_apply.argtypes = [
        ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte
    ]
    loaded.udeks_lifecycle_apply.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_get.argtypes = [ctypes.c_ubyte]
    loaded.udeks_lifecycle_get.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_parent.argtypes = [ctypes.c_ubyte]
    loaded.udeks_lifecycle_parent.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_wait_reason.argtypes = [ctypes.c_ubyte]
    loaded.udeks_lifecycle_wait_reason.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_exit_status.argtypes = [ctypes.c_ubyte]
    loaded.udeks_lifecycle_exit_status.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_publish.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte)
    ]
    loaded.udeks_lifecycle_publish.restype = None
    loaded.udeks_task_policy_validate.argtypes = [
        ctypes.c_ubyte,
        ctypes.c_ubyte,
        ctypes.c_ubyte,
        ctypes.c_ubyte,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_ubyte,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.POINTER(ctypes.c_uint),
    ]
    loaded.udeks_task_policy_validate.restype = ctypes.c_ubyte
    loaded.udeks_task_policy_validate_spawn_candidate.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_ubyte,
    ]
    loaded.udeks_task_policy_validate_spawn_candidate.restype = ctypes.c_ubyte
    return loaded


@unittest.skipUnless(CC, "host C compiler is unavailable")
class TaskPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.library = compile_library(cls.temporary.name)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.assertEqual(self.library.udeks_lifecycle_reset(), OK)

    def create(self, task_id, parent=0, flags=FLAG_USER):
        return self.library.udeks_lifecycle_create(task_id, parent, flags)

    def apply(self, task_id, event, argument=0):
        return self.library.udeks_lifecycle_apply(task_id, event, argument)

    def get(self, task_id):
        return self.library.udeks_lifecycle_get(task_id)

    def start_caller(self, caller=1):
        self.create(caller)
        self.apply(caller, ADMIT)
        self.apply(caller, DISPATCH)

    def add_child(self, child, parent=1):
        self.create(child, parent)
        self.apply(child, ADMIT)

    def exit_child(self, caller, child, status):
        self.apply(caller, YIELD)
        self.apply(child, DISPATCH)
        self.apply(child, EXIT, status)
        self.apply(caller, DISPATCH)

    def validate(self, operation, flags=0, count=0, payload=None, caller=1,
                 descriptor=0):
        buffer = (ctypes.c_ubyte * PAYLOAD_SIZE)()
        if payload:
            for index, value in enumerate(payload):
                buffer[index] = value
        task_id = ctypes.c_ubyte(0)
        status = ctypes.c_ubyte(0)
        ticks = ctypes.c_uint(0)
        result = self.library.udeks_task_policy_validate(
            operation,
            flags,
            count,
            descriptor,
            buffer,
            caller,
            ctypes.byref(task_id),
            ctypes.byref(status),
            ctypes.byref(ticks),
        )
        return result, task_id.value, status.value, ticks.value

    def make_candidate(self, magic=b"UDEX", major=0, cpu=1, flags=0,
                       image_base=0x0200, image_size=0x0800,
                       bss_size=0x0100, entry=0x0300, stack_base=0x1000,
                       stack_size=0x0100):
        candidate = (ctypes.c_ubyte * 19)()
        for index, value in enumerate(magic):
            candidate[index] = value
        candidate[4] = major
        candidate[5] = cpu
        candidate[6] = flags

        def word(offset, value):
            candidate[offset] = value & 0xFF
            candidate[offset + 1] = (value >> 8) & 0xFF

        word(7, image_base)
        word(9, image_size)
        word(11, bss_size)
        word(13, entry)
        word(15, stack_base)
        word(17, stack_size)
        return candidate

    def make_reserved(self, ranges):
        data = bytearray()
        for base, size in ranges:
            data += bytes(
                [base & 0xFF, (base >> 8) & 0xFF,
                 size & 0xFF, (size >> 8) & 0xFF]
            )
        return (ctypes.c_ubyte * len(data))(*data)

    def candidate_result(self, candidate, reserved=None, count=0):
        if reserved is None:
            reserved = (ctypes.c_ubyte * 1)()
            count = 0
        return self.library.udeks_task_policy_validate_spawn_candidate(
            candidate, reserved, count
        )

    def snapshot(self):
        record = (ctypes.c_ubyte * 16)()
        self.library.udeks_lifecycle_publish(record)
        tasks = tuple(
            (
                self.library.udeks_lifecycle_get(task_id),
                self.library.udeks_lifecycle_parent(task_id),
                self.library.udeks_lifecycle_wait_reason(task_id),
                self.library.udeks_lifecycle_exit_status(task_id),
            )
            for task_id in range(0, 10)
        )
        return bytes(record), tasks

    def test_unknown_operations_return_enosys(self):
        self.start_caller()
        for operation in (0, 1, 3, 9, 16):
            with self.subTest(operation=operation):
                result, _, _, _ = self.validate(operation)
                self.assertEqual(result, ENOSYS)

    def test_unknown_operation_precedes_other_validation(self):
        self.start_caller()
        self.assertEqual(
            self.validate(99, descriptor=1, caller=9)[0], ENOSYS
        )
        self.assertEqual(
            self.validate(1, flags=0x80, count=0, caller=9)[0], ENOSYS
        )
        self.assertEqual(
            self.validate(0, descriptor=1, payload=[9] * PAYLOAD_SIZE)[0],
            ENOSYS,
        )

    def test_yield_and_exit_validation(self):
        self.start_caller()
        self.assertEqual(self.validate(YIELD_OP, count=0)[0], OK)
        self.assertEqual(self.validate(YIELD_OP, count=1)[0], EINVAL)
        self.assertEqual(self.validate(YIELD_OP, flags=1)[0], EINVAL)

        result, task_id, status, _ = self.validate(
            EXIT_OP, count=1, payload=[7]
        )
        self.assertEqual(result, OK)
        self.assertEqual(task_id, 1)
        self.assertEqual(status, 7)
        self.assertEqual(self.validate(EXIT_OP, count=0)[0], EINVAL)
        self.assertEqual(self.validate(EXIT_OP, flags=1, count=1)[0], EINVAL)

    def test_waitpid_follows_linux_nohang_semantics(self):
        self.start_caller()
        self.add_child(2)

        result, task_id, status, _ = self.validate(
            WAITPID_OP, flags=NOHANG, count=2, payload=[2, 0]
        )
        self.assertEqual(result, OK)
        self.assertEqual(task_id, 2)
        self.assertEqual(status, 0)
        self.assertEqual(self.get(2), RUNNABLE)

        result, task_id, _, _ = self.validate(
            WAITPID_OP, flags=NOHANG, count=2, payload=[0, 0]
        )
        self.assertEqual(result, OK)
        self.assertEqual(task_id, 0)

        self.exit_child(1, 2, 7)
        result, task_id, status, _ = self.validate(
            WAITPID_OP, count=2, payload=[0, 0]
        )
        self.assertEqual(result, OK)
        self.assertEqual(task_id, 2)
        self.assertEqual(status, 7)
        self.assertEqual(self.get(2), ZOMBIE)

    def test_waitpid_rejects_non_children_and_bad_requests(self):
        self.start_caller()
        self.add_child(2)
        self.assertEqual(
            self.validate(WAITPID_OP, flags=NOHANG, count=2, payload=[0, 0])[0],
            OK,
        )

        self.create(3)
        self.apply(3, ADMIT)
        self.assertEqual(
            self.validate(WAITPID_OP, count=2, payload=[3, 0])[0], ECHILD
        )
        self.assertEqual(
            self.validate(WAITPID_OP, count=2, payload=[2, 1])[0], ECHILD
        )
        self.assertEqual(
            self.validate(WAITPID_OP, flags=0x02, count=2,
                          payload=[2, 0])[0],
            EINVAL,
        )
        self.assertEqual(
            self.validate(WAITPID_OP, count=1, payload=[2, 0])[0], EINVAL
        )

    def test_waitpid_without_children_returns_echild(self):
        self.start_caller()
        self.assertEqual(
            self.validate(WAITPID_OP, flags=NOHANG, count=2, payload=[0, 0])[0],
            ECHILD,
        )

    def test_cancel_validation(self):
        self.start_caller()
        self.add_child(2)
        result, task_id, status, _ = self.validate(
            CANCEL_OP, count=3, payload=[2, 0, 130]
        )
        self.assertEqual(result, OK)
        self.assertEqual(task_id, 2)
        self.assertEqual(status, 130)
        self.assertEqual(self.get(2), RUNNABLE)

        self.assertEqual(
            self.validate(CANCEL_OP, count=3, payload=[1, 0, 130])[0], EINVAL
        )
        self.assertEqual(
            self.validate(CANCEL_OP, count=3, payload=[0, 0, 130])[0], EINVAL
        )
        self.assertEqual(
            self.validate(CANCEL_OP, count=3, payload=[3, 0, 130])[0], ESRCH
        )
        self.create(4)
        self.apply(4, ADMIT)
        self.assertEqual(
            self.validate(CANCEL_OP, count=3, payload=[4, 0, 130])[0], ESRCH
        )
        self.assertEqual(
            self.validate(CANCEL_OP, count=3, payload=[2, 1, 130])[0], ESRCH
        )
        self.assertEqual(
            self.validate(CANCEL_OP, flags=1, count=3,
                          payload=[2, 0, 130])[0],
            EINVAL,
        )
        self.assertEqual(
            self.validate(CANCEL_OP, count=2, payload=[2, 0, 130])[0], EINVAL
        )

        self.exit_child(1, 2, 0)
        self.assertEqual(
            self.validate(CANCEL_OP, count=3, payload=[2, 0, 130])[0], ESRCH
        )

    def test_sleep_range_and_units(self):
        self.start_caller()
        result, _, _, ticks = self.validate(
            SLEEP_OP, count=2, payload=[1, 0]
        )
        self.assertEqual(result, OK)
        self.assertEqual(ticks, 1)
        result, _, _, ticks = self.validate(
            SLEEP_OP, count=2, payload=[0x58, 0x02]
        )
        self.assertEqual(result, OK)
        self.assertEqual(ticks, 600)
        self.assertEqual(
            self.validate(SLEEP_OP, count=2, payload=[0, 0])[0], EINVAL
        )
        self.assertEqual(
            self.validate(SLEEP_OP, count=2, payload=[0x59, 0x02])[0], EINVAL
        )
        self.assertEqual(
            self.validate(SLEEP_OP, flags=1, count=2, payload=[1, 0])[0],
            EINVAL,
        )
        self.assertEqual(
            self.validate(SLEEP_OP, count=1, payload=[1, 0])[0], EINVAL
        )

    def test_spawn_name_validation(self):
        self.start_caller()
        payload = [6] + list(b"cowsay") + [0] * 10
        self.assertEqual(self.validate(SPAWN_OP, count=17, payload=payload)[0], OK)
        self.assertEqual(
            self.validate(SPAWN_OP, count=17, payload=[0] + [0] * 16)[0],
            EINVAL,
        )
        self.assertEqual(
            self.validate(SPAWN_OP, count=17, payload=[17] + [0] * 16)[0],
            EINVAL,
        )
        padded = [6] + list(b"cowsay") + [1] + [0] * 9
        self.assertEqual(
            self.validate(SPAWN_OP, count=17, payload=padded)[0], EINVAL
        )
        bad_name = [6] + list(b"cow/sa") + [0] * 10
        self.assertEqual(
            self.validate(SPAWN_OP, count=17, payload=bad_name)[0], EINVAL
        )
        self.assertEqual(
            self.validate(SPAWN_OP, flags=1, count=17, payload=payload)[0],
            EINVAL,
        )
        self.assertEqual(
            self.validate(SPAWN_OP, count=16, payload=payload)[0], EINVAL
        )

    def test_waitpid_any_child_is_not_bound_to_the_first_live_child(self):
        self.start_caller()
        self.add_child(2)
        self.add_child(3)

        result, task_id, status, _ = self.validate(
            WAITPID_OP, flags=NOHANG, count=2, payload=[0, 0]
        )
        self.assertEqual(result, OK)
        self.assertEqual(task_id, 0)
        self.assertEqual(status, 0)

        self.exit_child(1, 3, 5)
        result, task_id, status, _ = self.validate(
            WAITPID_OP, count=2, payload=[0, 0]
        )
        self.assertEqual(result, OK)
        self.assertEqual(task_id, 3)
        self.assertEqual(status, 5)

    def test_lifecycle_operations_require_descriptor_zero(self):
        self.start_caller()
        self.add_child(2)
        cases = (
            (YIELD_OP, 0, 0, None),
            (EXIT_OP, 0, 1, [7]),
            (WAITPID_OP, NOHANG, 2, [0, 0]),
            (SLEEP_OP, 0, 2, [1, 0]),
            (CANCEL_OP, 0, 3, [2, 0, 130]),
            (SPAWN_OP, 0, 17, [6] + list(b"cowsay") + [0] * 10),
        )
        for operation, flags, count, payload in cases:
            with self.subTest(operation=operation):
                self.assertEqual(
                    self.validate(operation, flags=flags, count=count,
                                  payload=payload, descriptor=1)[0],
                    EINVAL,
                )

    def test_caller_must_be_the_current_running_task(self):
        self.start_caller()
        self.assertEqual(self.validate(YIELD_OP, count=0)[0], OK)

        self.apply(1, YIELD)
        self.assertEqual(self.validate(YIELD_OP, count=0)[0], EINVAL)

        self.apply(1, DISPATCH)
        self.assertEqual(self.validate(YIELD_OP, count=0)[0], OK)

        self.create(2, parent=1)
        self.apply(2, ADMIT)
        self.assertEqual(
            self.validate(YIELD_OP, count=0, caller=2)[0], EINVAL
        )

    def test_spawn_candidate_accepts_a_valid_placement(self):
        self.assertEqual(self.candidate_result(self.make_candidate()), OK)
        reserved = self.make_reserved(
            [(0x2000, 0xB000), (0xD000, 0x1000), (0xF000, 0x1000)]
        )
        self.assertEqual(
            self.candidate_result(self.make_candidate(), reserved, 3), OK
        )

    def test_spawn_candidate_rejects_bad_format_and_cpu(self):
        self.assertEqual(
            self.candidate_result(self.make_candidate(magic=b"UDEY")), ENOEXEC
        )
        self.assertEqual(
            self.candidate_result(self.make_candidate(major=1)), ENOEXEC
        )
        self.assertEqual(
            self.candidate_result(self.make_candidate(cpu=2)), ENOEXEC
        )
        self.assertEqual(
            self.candidate_result(self.make_candidate(flags=1)), ENOEXEC
        )
        self.assertEqual(
            self.candidate_result(self.make_candidate(image_size=0)), ENOEXEC
        )
        self.assertEqual(
            self.candidate_result(self.make_candidate(entry=0x0100)), ENOEXEC
        )

    def test_spawn_candidate_accepts_ranges_ending_at_address_space_top(self):
        self.assertEqual(
            self.candidate_result(
                self.make_candidate(
                    image_base=0xFF00, image_size=0x0100, bss_size=0,
                    entry=0xFF00, stack_base=0x0100, stack_size=0x0100,
                )
            ),
            OK,
        )
        self.assertEqual(
            self.candidate_result(
                self.make_candidate(
                    image_base=0x0200, image_size=0x0100, bss_size=0,
                    entry=0x0200, stack_base=0xFFE0, stack_size=0x0020,
                )
            ),
            OK,
        )
        reserved = self.make_reserved([(0xF000, 0x1000)])
        self.assertEqual(
            self.candidate_result(
                self.make_candidate(
                    image_base=0x0200, image_size=0x0100, bss_size=0,
                    entry=0x0200, stack_base=0xFFE0, stack_size=0x0020,
                ),
                reserved,
                1,
            ),
            ENOMEM,
        )

    def test_spawn_candidate_rejects_bad_stacks(self):
        self.assertEqual(
            self.candidate_result(self.make_candidate(stack_size=16)), EINVAL
        )
        self.assertEqual(
            self.candidate_result(
                self.make_candidate(stack_base=0xFF80, stack_size=0x100)
            ),
            EINVAL,
        )
        self.assertEqual(
            self.candidate_result(
                self.make_candidate(stack_base=0x0500, stack_size=0x0100)
            ),
            EINVAL,
        )

    def test_spawn_candidate_rejects_overflow_and_overlap(self):
        self.assertEqual(
            self.candidate_result(
                self.make_candidate(
                    image_base=0xF000, image_size=0x2000, entry=0xF000
                )
            ),
            ENOMEM,
        )
        self.assertEqual(
            self.candidate_result(
                self.make_candidate(
                    image_base=0xF000, image_size=0x0800, bss_size=0x1000,
                    entry=0xF000, stack_base=0x0100,
                )
            ),
            ENOMEM,
        )
        reserved = self.make_reserved([(0x0200, 0x0A00)])
        self.assertEqual(
            self.candidate_result(self.make_candidate(), reserved, 1), ENOMEM
        )
        reserved = self.make_reserved([(0x1000, 0x0100)])
        self.assertEqual(
            self.candidate_result(self.make_candidate(), reserved, 1), ENOMEM
        )
        reserved = self.make_reserved([(0x0B00, 0x0500)])
        self.assertEqual(
            self.candidate_result(self.make_candidate(), reserved, 1), OK
        )

    def test_invalid_caller_returns_esrch(self):
        self.assertEqual(self.validate(YIELD_OP, count=0, caller=9)[0], ESRCH)
        self.assertEqual(self.validate(YIELD_OP, count=0, caller=0)[0], ESRCH)

    def test_validation_never_mutates_the_table(self):
        self.start_caller()
        self.add_child(2)
        before = self.snapshot()

        self.validate(YIELD_OP, count=0)
        self.validate(EXIT_OP, count=1, payload=[7])
        self.validate(WAITPID_OP, flags=NOHANG, count=2, payload=[2, 0])
        self.validate(WAITPID_OP, count=2, payload=[0, 0])
        self.validate(SLEEP_OP, count=2, payload=[0x58, 0x02])
        self.validate(CANCEL_OP, count=3, payload=[2, 0, 130])
        self.validate(SPAWN_OP, count=2, payload=[1, 0])
        self.validate(CANCEL_OP, count=3, payload=[9, 0, 130])
        self.validate(WAITPID_OP, flags=0x80, count=2, payload=[2, 0])
        self.validate(99)
        self.candidate_result(self.make_candidate())
        self.candidate_result(self.make_candidate(cpu=2))
        reserved = self.make_reserved([(0x0200, 0x0A00)])
        self.candidate_result(self.make_candidate(), reserved, 1)

        self.assertEqual(self.snapshot(), before)


class TaskPolicySourceTests(unittest.TestCase):
    def test_policy_module_is_validation_only(self):
        source = (ROOT / "src/kernel/task_policy.c").read_text(encoding="utf-8")

        self.assertIn("udeks_task_policy_validate", source)
        self.assertIn("udeks_lifecycle_parent", source)
        self.assertNotIn("udeks_lifecycle_apply", source)
        self.assertNotIn("udeks_lifecycle_create", source)
        self.assertNotIn("udeks_lifecycle_reset", source)

    def test_makefile_builds_the_policy_for_cc65(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("task-policy", makefile)
        self.assertIn("task_policy.c", makefile)

    def test_header_declares_the_validator(self):
        header = (ROOT / "include/udeks/task_policy.h").read_text(
            encoding="utf-8"
        )

        self.assertIn("udeks_task_policy_validate", header)
        self.assertIn("udeks_task_policy_validate_spawn_candidate", header)
        self.assertIn("never mutate the task table", header)


if __name__ == "__main__":
    unittest.main()

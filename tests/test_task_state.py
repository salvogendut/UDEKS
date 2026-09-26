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

STATUS_BASE = 0xF110
STATUS_SIZE = 16
CLOCK_STATUS_BASE = 0xF100
CLOCK_STATUS_SIZE = 16
KEYBOARD_STATUS_BASE = 0xF120

FREE = 0
NEW = 1
RUNNABLE = 2
RUNNING = 3
WAITING = 4
STOPPED = 5
ZOMBIE = 6

ADMIT = 2
DISPATCH = 3
YIELD = 4
BLOCK = 5
UNBLOCK = 6
STOP = 7
CONTINUE = 8
EXIT = 9
REAP = 10
CANCEL = 11

WAIT_NONE = 0
WAIT_CHILD = 1
WAIT_INPUT = 2
WAIT_TERMINAL = 5

FLAG_USER = 0x01
FLAG_PERSISTENT = 0x02

OK = 0
BAD_ID = 1
BAD_STATE = 2
EXISTS = 3
BAD_REASON = 5
BUSY = 6
BAD_EVENT = 7
BAD_FLAGS = 8
INVALID = 0xFF


def c_defines(name: str) -> dict[str, int]:
    text = (ROOT / name).read_text(encoding="utf-8")
    values = {}
    for match in re.finditer(
        r"^#define\s+(UDEKS_[A-Z0-9_]+)\s+(0x[0-9A-Fa-f]+|\d+)(?:u|ul)?$",
        text,
        re.MULTILINE,
    ):
        values[match.group(1)] = int(match.group(2), 0)
    return values


def compile_library(directory: str) -> ctypes.CDLL:
    library = Path(directory) / "task_state.so"
    subprocess.run(
        [
            CC,
            "-std=c99",
            "-shared",
            "-fPIC",
            "-I",
            str(ROOT / "include"),
            str(ROOT / "src/kernel/task_state.c"),
            "-o",
            str(library),
        ],
        check=True,
        capture_output=True,
    )
    loaded = ctypes.CDLL(str(library))
    loaded.udeks_lifecycle_reset.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_create.argtypes = [
        ctypes.c_ubyte,
        ctypes.c_ubyte,
        ctypes.c_ubyte,
    ]
    loaded.udeks_lifecycle_create.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_apply.argtypes = [
        ctypes.c_ubyte,
        ctypes.c_ubyte,
        ctypes.c_ubyte,
    ]
    loaded.udeks_lifecycle_apply.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_get.argtypes = [ctypes.c_ubyte]
    loaded.udeks_lifecycle_get.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_wait_reason.argtypes = [ctypes.c_ubyte]
    loaded.udeks_lifecycle_wait_reason.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_exit_status.argtypes = [ctypes.c_ubyte]
    loaded.udeks_lifecycle_exit_status.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_current.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_runnable_count.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_defined_count.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_switch_count.restype = ctypes.c_uint
    loaded.udeks_lifecycle_rejected_count.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_canary_failures.restype = ctypes.c_ubyte
    loaded.udeks_lifecycle_note_canary_failure.restype = None
    loaded.udeks_lifecycle_publish.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte)
    ]
    loaded.udeks_lifecycle_publish.restype = None
    return loaded


@unittest.skipUnless(CC, "host C compiler is unavailable")
class LifecycleBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.state = compile_library(cls.temporary.name)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.assertEqual(self.state.udeks_lifecycle_reset(), OK)

    def create(self, task_id, parent=0, flags=FLAG_USER):
        return self.state.udeks_lifecycle_create(task_id, parent, flags)

    def apply(self, task_id, event, argument=0):
        return self.state.udeks_lifecycle_apply(task_id, event, argument)

    def publish(self) -> bytes:
        record = (ctypes.c_ubyte * STATUS_SIZE)()
        self.state.udeks_lifecycle_publish(record)
        return bytes(record)

    def test_reset_clears_table_and_counters(self):
        self.assertEqual(self.state.udeks_lifecycle_current(), 0)
        self.assertEqual(self.state.udeks_lifecycle_runnable_count(), 0)
        self.assertEqual(self.state.udeks_lifecycle_defined_count(), 0)
        self.assertEqual(self.state.udeks_lifecycle_switch_count(), 0)
        self.assertEqual(self.state.udeks_lifecycle_rejected_count(), 0)
        self.assertEqual(self.state.udeks_lifecycle_canary_failures(), 0)
        record = self.publish()
        self.assertEqual(record[:4], b"UTSK")
        self.assertEqual(record[4:6], b"\x00\x01")
        self.assertEqual(record[6], 1)
        self.assertEqual(record[15], 0)

    def test_create_validates_ids_slots_and_flags(self):
        self.assertEqual(self.create(1), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), NEW)
        self.assertEqual(self.create(1), EXISTS)
        self.assertEqual(self.create(0), BAD_ID)
        self.assertEqual(self.create(9), BAD_ID)
        self.assertEqual(self.create(2, flags=0x80), BAD_FLAGS)
        self.assertEqual(self.state.udeks_lifecycle_get(2), FREE)
        self.assertEqual(self.state.udeks_lifecycle_rejected_count(), 4)

    def test_parent_must_be_a_different_live_task(self):
        self.assertEqual(self.create(1), OK)
        self.assertEqual(self.create(1, parent=1), EXISTS)
        self.assertEqual(self.create(2, parent=1), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(2), NEW)
        self.assertEqual(self.create(3, parent=9), BAD_ID)
        self.assertEqual(self.create(4, parent=4), BAD_ID)
        self.assertEqual(self.create(5, parent=1), OK)
        self.assertEqual(self.state.udeks_lifecycle_rejected_count(), 3)

    def test_free_and_reaped_parents_are_rejected(self):
        self.create(1)
        self.assertEqual(self.create(2, parent=1), OK)
        self.apply(2, ADMIT)
        self.apply(2, DISPATCH)
        self.apply(2, EXIT, 0)
        self.apply(2, REAP)
        self.assertEqual(self.state.udeks_lifecycle_get(2), FREE)
        self.assertEqual(self.create(3, parent=2), BAD_ID)
        self.assertEqual(self.state.udeks_lifecycle_get(3), FREE)

    def test_zombie_parent_is_not_live(self):
        self.create(1)
        self.create(2, parent=1)
        self.apply(2, ADMIT, 0)
        self.apply(2, DISPATCH, 0)
        self.apply(2, EXIT, 0)
        self.assertEqual(self.state.udeks_lifecycle_get(2), ZOMBIE)
        self.assertEqual(self.create(3, parent=2), BAD_ID)
        self.assertEqual(self.state.udeks_lifecycle_get(3), FREE)

    def test_admit_and_dispatch_track_the_single_running_task(self):
        self.create(1)
        self.assertEqual(self.apply(1, DISPATCH), BAD_STATE)
        self.assertEqual(self.apply(1, ADMIT), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), RUNNABLE)
        self.assertEqual(self.apply(1, DISPATCH), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), RUNNING)
        self.assertEqual(self.state.udeks_lifecycle_current(), 1)
        self.assertEqual(self.state.udeks_lifecycle_switch_count(), 1)

        self.create(2, parent=1)
        self.apply(2, ADMIT, 0)
        self.assertEqual(self.apply(2, DISPATCH), BUSY)
        self.assertEqual(self.state.udeks_lifecycle_get(2), RUNNABLE)
        self.assertEqual(self.state.udeks_lifecycle_current(), 1)

        self.assertEqual(self.apply(1, YIELD), OK)
        self.assertEqual(self.state.udeks_lifecycle_current(), 0)
        self.assertEqual(self.apply(2, DISPATCH), OK)
        self.assertEqual(self.state.udeks_lifecycle_switch_count(), 2)

    def test_redispatch_of_the_current_task_is_a_noop(self):
        self.create(1)
        self.apply(1, ADMIT, 0)
        self.apply(1, DISPATCH, 0)
        self.assertEqual(self.apply(1, DISPATCH), OK)
        self.assertEqual(self.state.udeks_lifecycle_switch_count(), 1)
        self.assertEqual(self.state.udeks_lifecycle_current(), 1)

    def test_block_records_and_clears_the_wait_reason(self):
        self.create(1)
        self.apply(1, ADMIT, 0)
        self.apply(1, DISPATCH, 0)
        self.assertEqual(self.apply(1, BLOCK, WAIT_NONE), BAD_REASON)
        self.assertEqual(self.apply(1, BLOCK, 9), BAD_REASON)
        self.assertEqual(self.state.udeks_lifecycle_get(1), RUNNING)
        self.assertEqual(self.apply(1, BLOCK, WAIT_INPUT), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), WAITING)
        self.assertEqual(self.state.udeks_lifecycle_wait_reason(1), WAIT_INPUT)
        self.assertEqual(self.state.udeks_lifecycle_current(), 0)
        self.assertEqual(self.apply(1, UNBLOCK), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), RUNNABLE)
        self.assertEqual(self.state.udeks_lifecycle_wait_reason(1), WAIT_NONE)

    def test_stop_and_continue_preserve_a_wait_condition(self):
        self.create(1)
        self.apply(1, ADMIT, 0)
        self.apply(1, DISPATCH, 0)
        self.apply(1, BLOCK, WAIT_CHILD)
        self.assertEqual(self.apply(1, STOP), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), STOPPED)
        self.assertEqual(self.state.udeks_lifecycle_wait_reason(1), WAIT_CHILD)
        self.assertEqual(self.apply(1, CONTINUE), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), WAITING)
        self.assertEqual(self.state.udeks_lifecycle_wait_reason(1), WAIT_CHILD)
        self.assertEqual(self.apply(1, UNBLOCK), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), RUNNABLE)

    def test_stop_and_continue_return_a_runnable_task_to_runnable(self):
        self.create(1)
        self.apply(1, ADMIT, 0)
        self.assertEqual(self.apply(1, STOP), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), STOPPED)
        self.assertEqual(self.apply(1, CONTINUE), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), RUNNABLE)
        self.assertEqual(self.state.udeks_lifecycle_wait_reason(1), WAIT_NONE)

    def test_exit_records_status_and_reap_frees_the_slot(self):
        self.create(1)
        self.apply(1, ADMIT, 0)
        self.apply(1, DISPATCH, 0)
        self.assertEqual(self.apply(1, EXIT, 7), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), ZOMBIE)
        self.assertEqual(self.state.udeks_lifecycle_exit_status(1), 7)
        self.assertEqual(self.state.udeks_lifecycle_current(), 0)
        self.assertEqual(self.apply(1, REAP), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), FREE)
        self.assertEqual(self.state.udeks_lifecycle_exit_status(1), 0)
        self.assertEqual(self.create(1), OK)

    def test_cancel_records_the_termination_status(self):
        self.create(1)
        self.apply(1, ADMIT, 0)
        self.apply(1, DISPATCH, 0)
        self.assertEqual(self.apply(1, CANCEL, 130), OK)
        self.assertEqual(self.state.udeks_lifecycle_get(1), ZOMBIE)
        self.assertEqual(self.state.udeks_lifecycle_exit_status(1), 130)
        self.assertEqual(self.state.udeks_lifecycle_current(), 0)

    def test_reaped_slots_do_not_leak_metadata(self):
        self.create(1, flags=FLAG_PERSISTENT)
        self.apply(1, ADMIT, 0)
        self.apply(1, DISPATCH, 0)
        self.apply(1, EXIT, 42)
        self.assertEqual(self.apply(1, REAP), OK)
        self.assertEqual(self.state.udeks_lifecycle_exit_status(1), 0)
        self.assertEqual(self.create(1, parent=0, flags=0), OK)
        self.assertEqual(self.apply(1, ADMIT), OK)
        self.assertEqual(self.apply(1, DISPATCH), OK)
        record = self.publish()
        self.assertEqual(record[7], 1)
        self.assertEqual(record[8], 1)
        self.assertEqual(record[9], 1)

    def test_rejected_requests_do_not_change_state(self):
        self.create(1)
        self.apply(1, ADMIT, 0)
        before = self.state.udeks_lifecycle_rejected_count()
        self.assertEqual(self.apply(1, YIELD), BAD_STATE)
        self.assertEqual(self.apply(1, 0), BAD_EVENT)
        self.assertEqual(self.apply(1, 1), BAD_EVENT)
        self.assertEqual(self.state.udeks_lifecycle_get(1), RUNNABLE)
        self.assertEqual(self.state.udeks_lifecycle_current(), 0)
        self.assertEqual(self.state.udeks_lifecycle_switch_count(), 0)
        self.assertEqual(self.state.udeks_lifecycle_rejected_count(), before + 3)

    def test_invalid_ids_report_invalid_reads(self):
        self.assertEqual(self.state.udeks_lifecycle_get(0), INVALID)
        self.assertEqual(self.state.udeks_lifecycle_get(9), INVALID)
        self.assertEqual(self.state.udeks_lifecycle_wait_reason(0), INVALID)
        self.assertEqual(self.state.udeks_lifecycle_exit_status(0), INVALID)

    def test_table_accepts_every_bounded_id(self):
        for task_id in range(1, 9):
            self.assertEqual(self.create(task_id), OK)
        self.assertEqual(self.state.udeks_lifecycle_defined_count(), 8)
        self.assertEqual(self.state.udeks_lifecycle_runnable_count(), 0)
        self.assertEqual(self.create(9), BAD_ID)

    def test_publish_reports_derived_counts_and_switch_order(self):
        self.create(1)
        self.apply(1, ADMIT, 0)
        self.apply(1, DISPATCH, 0)
        self.create(2, parent=1)
        self.apply(2, ADMIT, 0)
        record = self.publish()
        self.assertEqual(record[7], 1)
        self.assertEqual(record[8], 2)
        self.assertEqual(record[9], 2)
        self.assertEqual(record[12], 1)
        self.assertEqual(record[13], 0)
        self.assertEqual(record[14], ADMIT)
        self.state.udeks_lifecycle_note_canary_failure()
        self.assertEqual(self.state.udeks_lifecycle_canary_failures(), 1)
        self.assertEqual(self.publish()[11], 1)


@unittest.skipUnless(CC, "host C compiler is unavailable")
class LifecycleUninitializedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.state = compile_library(cls.temporary.name)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_publish_before_reset_reports_an_uninitialized_table(self):
        record = (ctypes.c_ubyte * STATUS_SIZE)()
        self.state.udeks_lifecycle_publish(record)
        block = bytes(record)
        self.assertEqual(block[:4], b"UTSK")
        self.assertEqual(block[6], 0x81)
        self.assertEqual(block[8], 0)
        self.assertEqual(block[9], 0)


class LifecycleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.header = c_defines("include/udeks/task_state.h")
        cls.loader = c_defines("include/udeks/task.h")

    def test_lifecycle_macros_do_not_collide_with_the_loader_record(self):
        lifecycle = {
            name for name in self.header if name.startswith("UDEKS_LIFECYCLE_")
        }
        self.assertTrue(lifecycle)
        self.assertFalse(lifecycle & set(self.loader))
        self.assertNotIn("UDEKS_LIFECYCLE_STATE_RUNNING", self.loader)
        self.assertEqual(self.loader["UDEKS_TASK_STATE_RUNNING"], 2)
        self.assertEqual(self.header["UDEKS_LIFECYCLE_STATE_RUNNING"], 3)
        self.assertEqual(self.loader["UDEKS_TASK_BUSY"], 3)
        self.assertEqual(self.header["UDEKS_LIFECYCLE_BUSY"], 6)

    def test_header_state_and_event_values_are_frozen(self):
        header = self.header
        self.assertEqual(header["UDEKS_LIFECYCLE_STATUS_BASE"], STATUS_BASE)
        self.assertEqual(header["UDEKS_LIFECYCLE_STATUS_SIZE"], STATUS_SIZE)
        self.assertEqual(header["UDEKS_LIFECYCLE_MAX_TASKS"], 8)
        self.assertEqual(header["UDEKS_LIFECYCLE_INVALID"], INVALID)
        self.assertEqual(header["UDEKS_LIFECYCLE_STATE_FREE"], FREE)
        self.assertEqual(header["UDEKS_LIFECYCLE_STATE_NEW"], NEW)
        self.assertEqual(header["UDEKS_LIFECYCLE_STATE_RUNNABLE"], RUNNABLE)
        self.assertEqual(header["UDEKS_LIFECYCLE_STATE_RUNNING"], RUNNING)
        self.assertEqual(header["UDEKS_LIFECYCLE_STATE_WAITING"], WAITING)
        self.assertEqual(header["UDEKS_LIFECYCLE_STATE_STOPPED"], STOPPED)
        self.assertEqual(header["UDEKS_LIFECYCLE_STATE_ZOMBIE"], ZOMBIE)
        self.assertEqual(header["UDEKS_LIFECYCLE_EVENT_ADMIT"], ADMIT)
        self.assertEqual(header["UDEKS_LIFECYCLE_EVENT_DISPATCH"], DISPATCH)
        self.assertEqual(header["UDEKS_LIFECYCLE_EVENT_EXIT"], EXIT)
        self.assertEqual(header["UDEKS_LIFECYCLE_EVENT_CANCEL"], CANCEL)
        self.assertEqual(header["UDEKS_LIFECYCLE_WAIT_INPUT"], WAIT_INPUT)
        self.assertEqual(header["UDEKS_LIFECYCLE_FLAG_USER"], FLAG_USER)
        self.assertEqual(
            header["UDEKS_LIFECYCLE_FLAG_PERSISTENT"], FLAG_PERSISTENT
        )
        self.assertEqual(header["UDEKS_LIFECYCLE_OK"], OK)
        self.assertEqual(header["UDEKS_LIFECYCLE_BAD_ID"], BAD_ID)
        self.assertEqual(header["UDEKS_LIFECYCLE_BAD_STATE"], BAD_STATE)
        self.assertEqual(header["UDEKS_LIFECYCLE_EXISTS"], EXISTS)
        self.assertEqual(header["UDEKS_LIFECYCLE_BAD_REASON"], BAD_REASON)
        self.assertEqual(header["UDEKS_LIFECYCLE_BUSY"], BUSY)
        self.assertEqual(header["UDEKS_LIFECYCLE_BAD_EVENT"], BAD_EVENT)
        self.assertEqual(header["UDEKS_LIFECYCLE_BAD_FLAGS"], BAD_FLAGS)

    def test_status_record_does_not_overlap_neighbor_regions(self):
        memory = c_defines("include/udeks/memory.h")
        clock = c_defines("include/udeks/clock.h")
        keyboard = c_defines("include/udeks/keyboard.h")
        self.assertEqual(memory["UDEKS_COMMON_BASE"], 0xF000)
        self.assertEqual(clock["UDEKS_CLOCK_STATUS_BASE"], CLOCK_STATUS_BASE)
        self.assertEqual(
            CLOCK_STATUS_BASE + clock["UDEKS_CLOCK_STATUS_SIZE"],
            STATUS_BASE,
        )
        self.assertEqual(
            STATUS_BASE + STATUS_SIZE,
            keyboard["UDEKS_KEYBOARD_STATUS_BASE"],
        )
        self.assertEqual(STATUS_BASE + STATUS_SIZE, KEYBOARD_STATUS_BASE)
        self.assertGreaterEqual(STATUS_BASE, memory["UDEKS_COMMON_BASE"])
        self.assertLessEqual(
            STATUS_BASE + STATUS_SIZE, memory["UDEKS_COMMON_LIMIT"]
        )

    def test_abi_document_publishes_the_same_record(self):
        document = (ROOT / "abi/tasks.md").read_text(encoding="utf-8")
        self.assertIn("$F110-$F11F", document)
        self.assertIn("`UTSK`", document)
        self.assertIn("`UDEKS_LIFECYCLE_*`", document)
        for name in (
            "FREE",
            "NEW",
            "RUNNABLE",
            "RUNNING",
            "WAITING",
            "STOPPED",
            "ZOMBIE",
            "DISPATCH",
            "REAP",
            "CANCEL",
        ):
            self.assertIn(f"`{name}`", document)


if __name__ == "__main__":
    unittest.main()

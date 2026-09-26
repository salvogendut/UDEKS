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

OK = 0
BAD_ID = 1
BAD_STATE = 2
EXISTS = 3
BAD_REASON = 5
BUSY = 6
BAD_EVENT = 7


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
    loaded.udeks_task_state_reset.restype = ctypes.c_ubyte
    loaded.udeks_task_state_create.argtypes = [
        ctypes.c_ubyte,
        ctypes.c_ubyte,
        ctypes.c_ubyte,
    ]
    loaded.udeks_task_state_create.restype = ctypes.c_ubyte
    loaded.udeks_task_state_apply.argtypes = [
        ctypes.c_ubyte,
        ctypes.c_ubyte,
        ctypes.c_ubyte,
    ]
    loaded.udeks_task_state_apply.restype = ctypes.c_ubyte
    loaded.udeks_task_state_get.argtypes = [ctypes.c_ubyte]
    loaded.udeks_task_state_get.restype = ctypes.c_ubyte
    loaded.udeks_task_state_current.restype = ctypes.c_ubyte
    loaded.udeks_task_state_runnable_count.restype = ctypes.c_ubyte
    loaded.udeks_task_state_defined_count.restype = ctypes.c_ubyte
    loaded.udeks_task_state_switch_count.restype = ctypes.c_uint
    loaded.udeks_task_state_rejected_count.restype = ctypes.c_ubyte
    loaded.udeks_task_state_canary_failures.restype = ctypes.c_ubyte
    loaded.udeks_task_state_note_canary_failure.restype = None
    loaded.udeks_task_state_publish.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte)
    ]
    loaded.udeks_task_state_publish.restype = None
    return loaded


@unittest.skipUnless(CC, "host C compiler is unavailable")
class TaskStateBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.state = compile_library(cls.temporary.name)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.assertEqual(self.state.udeks_task_state_reset(), OK)

    def publish(self) -> bytes:
        record = (ctypes.c_ubyte * STATUS_SIZE)()
        self.state.udeks_task_state_publish(record)
        return bytes(record)

    def test_reset_clears_table_and_counters(self):
        self.assertEqual(self.state.udeks_task_state_current(), 0)
        self.assertEqual(self.state.udeks_task_state_runnable_count(), 0)
        self.assertEqual(self.state.udeks_task_state_defined_count(), 0)
        self.assertEqual(self.state.udeks_task_state_switch_count(), 0)
        self.assertEqual(self.state.udeks_task_state_rejected_count(), 0)
        self.assertEqual(self.state.udeks_task_state_canary_failures(), 0)
        record = self.publish()
        self.assertEqual(record[:4], b"UTSK")
        self.assertEqual(record[4:6], b"\x00\x01")
        self.assertEqual(record[6], 1)
        self.assertEqual(record[15], 0)

    def test_create_validates_ids_slots_and_parents(self):
        self.assertEqual(self.state.udeks_task_state_create(1, 0, 1), OK)
        self.assertEqual(self.state.udeks_task_state_get(1), NEW)
        self.assertEqual(self.state.udeks_task_state_create(1, 0, 0), EXISTS)
        self.assertEqual(self.state.udeks_task_state_create(0, 0, 0), BAD_ID)
        self.assertEqual(self.state.udeks_task_state_create(9, 0, 0), BAD_ID)
        self.assertEqual(self.state.udeks_task_state_create(2, 99, 0), BAD_ID)
        self.assertEqual(self.state.udeks_task_state_get(2), FREE)
        self.assertEqual(self.state.udeks_task_state_rejected_count(), 4)

    def test_admit_and_dispatch_track_the_single_running_task(self):
        self.state.udeks_task_state_create(1, 0, 1)
        self.assertEqual(
            self.state.udeks_task_state_apply(1, DISPATCH, 0), BAD_STATE
        )
        self.assertEqual(self.state.udeks_task_state_apply(1, ADMIT, 0), OK)
        self.assertEqual(self.state.udeks_task_state_get(1), RUNNABLE)
        self.assertEqual(self.state.udeks_task_state_apply(1, DISPATCH, 0), OK)
        self.assertEqual(self.state.udeks_task_state_get(1), RUNNING)
        self.assertEqual(self.state.udeks_task_state_current(), 1)
        self.assertEqual(self.state.udeks_task_state_switch_count(), 1)

        self.state.udeks_task_state_create(2, 1, 1)
        self.state.udeks_task_state_apply(2, ADMIT, 0)
        self.assertEqual(self.state.udeks_task_state_apply(2, DISPATCH, 0), BUSY)
        self.assertEqual(self.state.udeks_task_state_get(2), RUNNABLE)
        self.assertEqual(self.state.udeks_task_state_current(), 1)

        self.assertEqual(self.state.udeks_task_state_apply(1, YIELD, 0), OK)
        self.assertEqual(self.state.udeks_task_state_current(), 0)
        self.assertEqual(self.state.udeks_task_state_apply(2, DISPATCH, 0), OK)
        self.assertEqual(self.state.udeks_task_state_switch_count(), 2)

    def test_redispatch_of_the_current_task_is_a_noop(self):
        self.state.udeks_task_state_create(1, 0, 1)
        self.state.udeks_task_state_apply(1, ADMIT, 0)
        self.state.udeks_task_state_apply(1, DISPATCH, 0)
        self.assertEqual(self.state.udeks_task_state_apply(1, DISPATCH, 0), OK)
        self.assertEqual(self.state.udeks_task_state_switch_count(), 1)
        self.assertEqual(self.state.udeks_task_state_current(), 1)

    def test_block_requires_a_valid_reason(self):
        self.state.udeks_task_state_create(1, 0, 1)
        self.state.udeks_task_state_apply(1, ADMIT, 0)
        self.state.udeks_task_state_apply(1, DISPATCH, 0)
        self.assertEqual(
            self.state.udeks_task_state_apply(1, BLOCK, 0), BAD_REASON
        )
        self.assertEqual(self.state.udeks_task_state_get(1), RUNNING)
        self.assertEqual(
            self.state.udeks_task_state_apply(1, BLOCK, 9), BAD_REASON
        )
        self.assertEqual(self.state.udeks_task_state_apply(1, BLOCK, 2), OK)
        self.assertEqual(self.state.udeks_task_state_get(1), WAITING)
        self.assertEqual(self.state.udeks_task_state_current(), 0)
        self.assertEqual(self.state.udeks_task_state_apply(1, UNBLOCK, 0), OK)
        self.assertEqual(self.state.udeks_task_state_get(1), RUNNABLE)

    def test_stop_continue_and_cancel(self):
        self.state.udeks_task_state_create(1, 0, 1)
        self.state.udeks_task_state_apply(1, ADMIT, 0)
        self.assertEqual(self.state.udeks_task_state_apply(1, STOP, 0), OK)
        self.assertEqual(self.state.udeks_task_state_get(1), STOPPED)
        self.assertEqual(
            self.state.udeks_task_state_apply(1, DISPATCH, 0), BAD_STATE
        )
        self.assertEqual(self.state.udeks_task_state_apply(1, CONTINUE, 0), OK)
        self.assertEqual(self.state.udeks_task_state_get(1), RUNNABLE)
        self.assertEqual(self.state.udeks_task_state_apply(1, CANCEL, 0), OK)
        self.assertEqual(self.state.udeks_task_state_get(1), ZOMBIE)
        self.assertEqual(
            self.state.udeks_task_state_apply(1, CANCEL, 0), BAD_STATE
        )

    def test_exit_records_status_and_reap_frees_the_slot(self):
        self.state.udeks_task_state_create(1, 0, 1)
        self.state.udeks_task_state_apply(1, ADMIT, 0)
        self.state.udeks_task_state_apply(1, DISPATCH, 0)
        self.assertEqual(self.state.udeks_task_state_apply(1, EXIT, 7), OK)
        self.assertEqual(self.state.udeks_task_state_get(1), ZOMBIE)
        self.assertEqual(self.state.udeks_task_state_current(), 0)
        self.assertEqual(self.state.udeks_task_state_apply(1, REAP, 0), OK)
        self.assertEqual(self.state.udeks_task_state_get(1), FREE)
        self.assertEqual(self.state.udeks_task_state_create(1, 0, 1), OK)

    def test_rejected_requests_do_not_change_state(self):
        self.state.udeks_task_state_create(1, 0, 1)
        self.state.udeks_task_state_apply(1, ADMIT, 0)
        before = self.state.udeks_task_state_rejected_count()
        self.assertEqual(self.state.udeks_task_state_apply(1, YIELD, 0), BAD_STATE)
        self.assertEqual(self.state.udeks_task_state_apply(1, 0, 0), BAD_EVENT)
        self.assertEqual(self.state.udeks_task_state_apply(1, 1, 0), BAD_EVENT)
        self.assertEqual(self.state.udeks_task_state_get(1), RUNNABLE)
        self.assertEqual(self.state.udeks_task_state_current(), 0)
        self.assertEqual(self.state.udeks_task_state_switch_count(), 0)
        self.assertEqual(
            self.state.udeks_task_state_rejected_count(), before + 3
        )

    def test_table_accepts_every_bounded_id(self):
        for task_id in range(1, 9):
            self.assertEqual(
                self.state.udeks_task_state_create(task_id, 0, 1), OK
            )
        self.assertEqual(self.state.udeks_task_state_defined_count(), 8)
        self.assertEqual(self.state.udeks_task_state_runnable_count(), 0)
        self.assertEqual(self.state.udeks_task_state_create(9, 0, 0), BAD_ID)

    def test_publish_reports_derived_counts_and_switch_order(self):
        self.state.udeks_task_state_create(1, 0, 1)
        self.state.udeks_task_state_apply(1, ADMIT, 0)
        self.state.udeks_task_state_apply(1, DISPATCH, 0)
        self.state.udeks_task_state_create(2, 1, 1)
        self.state.udeks_task_state_apply(2, ADMIT, 0)
        record = self.publish()
        self.assertEqual(record[7], 1)
        self.assertEqual(record[8], 2)
        self.assertEqual(record[9], 2)
        self.assertEqual(record[12], 1)
        self.assertEqual(record[13], 0)
        self.assertEqual(record[14], ADMIT)
        self.state.udeks_task_state_note_canary_failure()
        self.assertEqual(self.state.udeks_task_state_canary_failures(), 1)
        self.assertEqual(self.publish()[11], 1)


@unittest.skipUnless(CC, "host C compiler is unavailable")
class TaskStateUninitializedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.state = compile_library(cls.temporary.name)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_publish_before_reset_reports_an_uninitialized_table(self):
        record = (ctypes.c_ubyte * STATUS_SIZE)()
        self.state.udeks_task_state_publish(record)
        block = bytes(record)
        self.assertEqual(block[:4], b"UTSK")
        self.assertEqual(block[6], 0x81)
        self.assertEqual(block[8], 0)
        self.assertEqual(block[9], 0)


class TaskStateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.header = c_defines("include/udeks/task_state.h")

    def test_header_state_and_event_values_are_frozen(self):
        header = self.header
        self.assertEqual(header["UDEKS_TASK_STATE_STATUS_BASE"], STATUS_BASE)
        self.assertEqual(header["UDEKS_TASK_STATE_STATUS_SIZE"], STATUS_SIZE)
        self.assertEqual(header["UDEKS_TASK_MAX_TASKS"], 8)
        self.assertEqual(header["UDEKS_TASK_STATE_FREE"], FREE)
        self.assertEqual(header["UDEKS_TASK_STATE_NEW"], NEW)
        self.assertEqual(header["UDEKS_TASK_STATE_RUNNABLE"], RUNNABLE)
        self.assertEqual(header["UDEKS_TASK_STATE_RUNNING"], RUNNING)
        self.assertEqual(header["UDEKS_TASK_STATE_WAITING"], WAITING)
        self.assertEqual(header["UDEKS_TASK_STATE_STOPPED"], STOPPED)
        self.assertEqual(header["UDEKS_TASK_STATE_ZOMBIE"], ZOMBIE)
        self.assertEqual(header["UDEKS_TASK_EVENT_ADMIT"], ADMIT)
        self.assertEqual(header["UDEKS_TASK_EVENT_DISPATCH"], DISPATCH)
        self.assertEqual(header["UDEKS_TASK_EVENT_EXIT"], EXIT)
        self.assertEqual(header["UDEKS_TASK_EVENT_CANCEL"], CANCEL)
        self.assertEqual(header["UDEKS_TASK_OK"], OK)
        self.assertEqual(header["UDEKS_TASK_BAD_ID"], BAD_ID)
        self.assertEqual(header["UDEKS_TASK_BAD_STATE"], BAD_STATE)
        self.assertEqual(header["UDEKS_TASK_EXISTS"], EXISTS)
        self.assertEqual(header["UDEKS_TASK_BAD_REASON"], BAD_REASON)
        self.assertEqual(header["UDEKS_TASK_BUSY"], BUSY)
        self.assertEqual(header["UDEKS_TASK_BAD_EVENT"], BAD_EVENT)

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

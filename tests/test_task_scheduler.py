# SPDX-License-Identifier: GPL-3.0-or-later

import ctypes
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CC = shutil.which("cc")

OK = 0
ADMIT = 2
DISPATCH = 3
YIELD = 4


def compile_library(directory: str) -> ctypes.CDLL:
    library = Path(directory) / "task_scheduler.so"
    subprocess.run(
        [
            CC,
            "-std=c99",
            "-shared",
            "-fPIC",
            "-I",
            str(ROOT / "include"),
            str(ROOT / "src/kernel/task_state.c"),
            str(ROOT / "src/kernel/task_scheduler.c"),
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
    loaded.udeks_scheduler_select_next.argtypes = [ctypes.c_ubyte]
    loaded.udeks_scheduler_select_next.restype = ctypes.c_ubyte
    return loaded


@unittest.skipUnless(CC, "host C compiler is unavailable")
class SchedulerPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.scheduler = compile_library(cls.temporary.name)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.assertEqual(self.scheduler.udeks_lifecycle_reset(), OK)

    def make_runnable(self, task_id):
        self.assertEqual(
            self.scheduler.udeks_lifecycle_create(task_id, 0, 1), OK
        )
        self.assertEqual(
            self.scheduler.udeks_lifecycle_apply(task_id, ADMIT, 0), OK
        )

    def test_empty_table_has_no_runnable_task(self):
        self.assertEqual(self.scheduler.udeks_scheduler_select_next(0), 0)

    def test_selection_is_round_robin_and_wraps(self):
        self.make_runnable(2)
        self.make_runnable(5)
        self.assertEqual(self.scheduler.udeks_scheduler_select_next(0), 2)
        self.assertEqual(self.scheduler.udeks_scheduler_select_next(2), 5)
        self.assertEqual(self.scheduler.udeks_scheduler_select_next(5), 2)

    def test_running_task_is_not_selected_until_it_yields(self):
        self.make_runnable(1)
        self.make_runnable(2)
        self.assertEqual(
            self.scheduler.udeks_lifecycle_apply(1, DISPATCH, 0), OK
        )
        self.assertEqual(self.scheduler.udeks_scheduler_select_next(2), 2)
        self.assertEqual(
            self.scheduler.udeks_lifecycle_apply(1, YIELD, 0), OK
        )
        self.assertEqual(self.scheduler.udeks_scheduler_select_next(2), 1)

    def test_zero_cursor_starts_at_task_one(self):
        self.make_runnable(1)
        self.make_runnable(8)
        self.assertEqual(self.scheduler.udeks_scheduler_select_next(0), 1)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TaskSwitchTailContractTests(unittest.TestCase):
    def test_tail_preserves_the_frozen_vectors_and_reservation(self):
        source = (ROOT / "src/8502/task_switch_tail.s").read_text().lower()
        config = (ROOT / "cfg/8502-task-switch-tail.cfg").read_text().lower()
        self.assertIn(".assert * = $ff10", source)
        self.assertIn("_udeks_task_switch_reset_gate:", source)
        self.assertIn("_udeks_task_switch_poll_gate:", source)
        self.assertIn("_udeks_task_switch_request_gate:", source)
        self.assertIn("task_switch_tail_end <= $ffc5", source)
        self.assertIn("start = $ff05, size = $00c0", config)
        self.assertNotIn(".res $07", source)

    def test_request_captures_before_selecting_the_kernel_mapping(self):
        source = (ROOT / "src/8502/task_switch_tail.s").read_text().lower()
        request = source.index("tail_request:")
        save_sp = source.index("stx context_sp", request)
        kernel = source.index("sta mmu_lcr_kernel_io", save_sp)
        dispatch = source.index("jsr task_request_dispatch", kernel)
        self.assertLess(request, save_sp)
        self.assertLess(save_sp, kernel)
        self.assertLess(kernel, dispatch)

    def test_dispatcher_carry_controls_suspend_vs_resume(self):
        source = (ROOT / "src/8502/task_switch_tail.s").read_text().lower()
        dispatch = source.index("jsr task_request_dispatch")
        self.assertIn("bcs tail_suspend", source[dispatch:])
        self.assertIn("jmp tail_restore", source[dispatch:])
        self.assertIn("tail_request_resume:\n        rts", source)


if __name__ == "__main__":
    unittest.main()

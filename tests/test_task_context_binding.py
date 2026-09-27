# SPDX-License-Identifier: GPL-3.0-or-later

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TaskContextBindingTests(unittest.TestCase):
    def test_common_record_is_shared_and_frozen(self):
        contract = (
            ROOT / "src/8502/task_switch_context.inc"
        ).read_text().lower()
        tail = (ROOT / "src/8502/task_switch_tail.s").read_text().lower()
        context = (
            ROOT / "src/scheduler/task_context.s"
        ).read_text().lower()
        self.assertIn("task_switch_context       = $ffb9", contract)
        self.assertIn("task_switch_context_size  = $0b", contract)
        self.assertIn("context_a = task_switch_context", tail)
        self.assertIn('include "task_switch_context.inc"', context)

    def test_scheduler_page_ends_with_fixed_callback_vectors(self):
        vectors = (
            ROOT / "src/scheduler/task_context_vectors.s"
        ).read_text().lower()
        tail = (ROOT / "src/8502/task_switch_tail.s").read_text().lower()
        self.assertIn(".assert * = $1ffa", vectors)
        self.assertIn(".assert * = $2000", vectors)
        self.assertIn("scheduler_reset         = $1ffa", tail)
        self.assertIn("scheduler_select        = $1ffd", tail)

    def test_task_one_owns_distinct_relocated_pages(self):
        source = (
            ROOT / "src/scheduler/task_context.s"
        ).read_text().lower()
        self.assertIn("task_page0              = $d1", source)
        self.assertIn("task_page1              = $d2", source)
        self.assertIn("task_page_bank          = $01", source)
        self.assertIn("task_soft_stack         = $eff0", source)
        self.assertIn("task_contexts:          .res task_count * task_context_size", source)

    def test_context_is_saved_before_lifecycle_mutation(self):
        source = (
            ROOT / "src/scheduler/task_context.s"
        ).read_text().lower()
        self.assertIn("_udeks_task_context_save_current:", source)
        self.assertIn("lda task_switch_context,y", source)
        self.assertIn("jsr _udeks_scheduler_select_next", source)
        self.assertIn("jsr _udeks_lifecycle_apply", source)

    def test_selected_record_uses_the_preserved_task_id(self):
        source = (
            ROOT / "src/scheduler/task_context.s"
        ).read_text().lower()
        self.assertIn(
            "load_selected:\n        jsr _udeks_task_wait_publish_current\n"
            "        lda current_task\n"
            "        jsr context_pointer",
            source,
        )

    def test_wait_state_is_reset_and_published_at_context_boundaries(self):
        context = (ROOT / "src/scheduler/task_context.s").read_text().lower()
        wait_state = (
            ROOT / "src/scheduler/task_wait_state.s"
        ).read_text().lower()
        self.assertIn("jsr _udeks_task_wait_reset", context)
        self.assertIn("jsr _udeks_task_wait_publish_current", context)
        for field in (
            "state", "operation", "sequence", "descriptor", "count",
            "flags", "selector", "selector_high", "child", "status",
        ):
            self.assertRegex(
                wait_state,
                re.escape(f"_udeks_task_wait_{field}_private:")
                + r"\s+\.res task_count",
            )
        self.assertLess(
            wait_state.rfind("sta _udeks_task_wait_state_private,x"),
            wait_state.rfind("sta treq_state"),
        )


if __name__ == "__main__":
    unittest.main()

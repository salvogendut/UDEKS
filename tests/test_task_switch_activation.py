# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_scheduler_overlay import build_overlay  # noqa: E402


def overlay_map() -> str:
    return """\
Segment list:
-------------
Name Start End Size Align
SCHEDULER 001C00 001FF9 0003FA 00001
CODE 00C120 00C126 000007 00001
BSS 00C127 00C129 000003 00001
"""


def context_map() -> str:
    return """\
Segment list:
-------------
Name Start End Size Align
CODE 00CDBD 00CE9E 0000E2 00001
RODATA 00CE9F 00CEA6 000008 00001
BSS 00CEA7 00CEFF 000059 00001
"""


class TaskSwitchActivationTests(unittest.TestCase):
    def test_overlay_carries_vectors_context_and_tail(self):
        page = bytes(0x400)
        tail = b"tail123"
        context = bytes((index % 251) + 1 for index in range(0xEA))
        switch_tail = bytes((index % 249) + 1 for index in range(0xC0))
        yield_handler = b"yield-handler"
        vectors = b"ABCDEF"
        payload, constants = build_overlay(
            page, tail, overlay_map(), context, context_map(), switch_tail,
            yield_handler, vectors,
        )
        body = payload[2 + 20:]
        self.assertEqual(body[:0x3FA], bytes(0x3FA))
        self.assertEqual(body[0x3FA:0x400], vectors)
        self.assertEqual(body[0x400:0x407], tail)
        self.assertEqual(body[0x407:0xDE0], bytes(0x9D9))
        self.assertEqual(body[0xDE0:0xDED], yield_handler)
        self.assertEqual(body[0xDED:0xED7], context)
        self.assertEqual(body[0xED7:0xF97], switch_tail)
        self.assertEqual(len(body), 0xF97)
        self.assertIn("SCHEDULER_OVERLAY_TAIL_SIZE = $09ed", constants)
        self.assertIn("TASK_ACTIVATION_CONTEXT_SOURCE = $5e01", constants)
        self.assertIn("TASK_ACTIVATION_CONTEXT_IMAGE_SIZE = $ea", constants)
        self.assertIn("TASK_ACTIVATION_CONTEXT_BSS_SIZE = $59", constants)
        self.assertIn("TASK_ACTIVATION_TAIL_SOURCE = $5eeb", constants)
        self.assertIn("TASK_ACTIVATION_TAIL_SIZE = $c0", constants)
        self.assertNotIn("TASK_ACTIVATION_YIELD", constants)

    def test_activation_fits_the_only_contiguous_post_console_window(self):
        config = (ROOT / "cfg/8502-task-switch-activation.cfg").read_text(
            encoding="utf-8"
        ).lower()
        source = (ROOT / "src/boot/task-switch-activation.s").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("app:    start = $1baa, size = $003e", config)
        self.assertIn("common: start = $f68a, size = $003e", config)
        self.assertIn("activation_common_end-activation_common <= $3e", source)
        self.assertIn("sta mmu_lcr_worker_flat", source)
        self.assertIn("sta mmu_lcr_kernel_io", source)
        self.assertIn("sta task_activation_tail_destination,y", source)
        self.assertNotIn("task_activation_yield", source)
        self.assertIn("jsr $ff10", source)
        installer = (ROOT / "src/boot/boot-console-installer.s").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("sta $f68a,y", installer)

    def test_bootstrap_tail_calls_activation_before_its_prefix_is_replaced(self):
        scheduler = (ROOT / "src/scheduler/scheduler.s").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("jsr _udeks_lifecycle_bootstrap", scheduler)
        self.assertIn("jmp $f68a", scheduler)

    def test_installer_clears_the_expanded_bss_with_unsigned_countdown(self):
        source = (
            ROOT / "src/boot/scheduler-tail-installer.s"
        ).read_text().lower()
        self.assertIn("ldy #scheduler_overlay_bss_size", source)
        self.assertIn(
            "clear_bss:\n        dey\n"
            "        sta scheduler_overlay_bss,y\n"
            "        bne clear_bss",
            source,
        )
        self.assertIn("scheduler_overlay_bss_size <= $ff", source)

    def test_lifecycle_handler_yields_exits_and_reaps_nonblocking(self):
        source = (ROOT / "src/scheduler/task_yield_handler.s").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("jsr _udeks_task_context_save_current", source)
        self.assertIn("jsr current_slot", source)
        self.assertIn("sta _udeks_lifecycle_slots_private+task_slot_state,x", source)
        self.assertIn("sta _udeks_lifecycle_slots_private+task_slot_exit,x", source)
        self.assertIn("request_waitpid:", source)
        self.assertIn("wait_any_child:", source)
        self.assertIn("wait_reap:", source)
        self.assertIn("jmp _udeks_bootfs_finish_ok", source)
        self.assertIn("lda #err_echild", source)
        self.assertIn("sta _udeks_lifecycle_last_event_private", source)
        self.assertIn("sta treq_state", source)
        self.assertIn("sec", source)
        self.assertIn("yield_invalid:", source)
        self.assertIn("jmp _udeks_bootfs_finish_error", source)
        self.assertIn("wait_blocking:", source)
        self.assertIn("sta _udeks_task_wait_sequence_private,y", source)
        self.assertIn("sta _udeks_task_wait_state_private,y", source)
        self.assertIn("_udeks_task_yield_handler = $cb00", source)
        self.assertIn("yield_handler_end <= $cdbd", source)


if __name__ == "__main__":
    unittest.main()

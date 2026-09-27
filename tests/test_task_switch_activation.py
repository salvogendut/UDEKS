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
CODE 00CDC3 00CEA3 0000E1 00001
BSS 00CEA4 00CEFC 000059 00001
"""


class TaskSwitchActivationTests(unittest.TestCase):
    def test_overlay_carries_vectors_context_and_tail(self):
        page = bytes(0x400)
        tail = b"tail123"
        context = bytes((index % 251) + 1 for index in range(0xE1))
        switch_tail = bytes((index % 249) + 1 for index in range(0xC0))
        vectors = b"ABCDEF"
        payload, constants = build_overlay(
            page, tail, overlay_map(), context, context_map(), switch_tail,
            vectors,
        )
        body = payload[2 + 20:]
        self.assertEqual(body[:0x3FA], bytes(0x3FA))
        self.assertEqual(body[0x3FA:0x400], vectors)
        self.assertEqual(body[0x400:0x407], tail)
        self.assertEqual(body[0x407:0x4E8], context)
        self.assertEqual(body[0x4E8:], switch_tail)
        self.assertIn("TASK_ACTIVATION_CONTEXT_SOURCE = $541b", constants)
        self.assertIn("TASK_ACTIVATION_CONTEXT_IMAGE_SIZE = $e1", constants)
        self.assertIn("TASK_ACTIVATION_CONTEXT_BSS_SIZE = $59", constants)
        self.assertIn("TASK_ACTIVATION_TAIL_SOURCE = $54fc", constants)
        self.assertIn("TASK_ACTIVATION_TAIL_SIZE = $c0", constants)

    def test_activation_fits_the_only_contiguous_post_console_window(self):
        config = (ROOT / "cfg/8502-task-switch-activation.cfg").read_text(
            encoding="utf-8"
        ).lower()
        source = (ROOT / "src/boot/task-switch-activation.s").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("app:    start = $1baa, size = $003e", config)
        self.assertIn("common: start = $f68a, size = $003e", config)
        self.assertIn("activation_common_end-activation_common <= $30", source)
        self.assertIn("sta mmu_lcr_worker_flat", source)
        self.assertIn("sta mmu_lcr_kernel_io", source)
        self.assertIn("sta task_activation_tail_destination,y", source)
        installer = (ROOT / "src/boot/boot-console-installer.s").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("sta $f68a,y", installer)

    def test_delivery_is_dormant_until_yield_is_integrated(self):
        init = (ROOT / "src/services/init/descriptor.s").read_text(
            encoding="utf-8"
        ).lower()
        self.assertNotIn("$1baa", init)
        self.assertIn("jsr lifecycle_bootstrap", init)


if __name__ == "__main__":
    unittest.main()

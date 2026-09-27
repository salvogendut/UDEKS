# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gen_task_context_imports as gen


def qualified_map() -> str:
    return """Segment list:
-------------
Name Start End Size Align
SCHEDULER 001C00 001FF9 0003FA 00001
CODE 00C120 00C4FD 0003DE 00001
RODATA 00C4FE 00C51C 00001F 00001
BSS 00C51D 00C58B 00006F 00001

Exports list by name:
---------------------
_udeks_lifecycle_apply 001C2E RLA
_udeks_scheduler_select_next 001FBB RLA
_udeks_task_wait_publish_current 00C494 RLA
_udeks_task_wait_reset 00C47D RLA
decsp2 008F94 REA
ptr1 00000E REZ
sp 000006 REZ

Exports list by value:
"""


class TaskContextImportTests(unittest.TestCase):
    def test_qualified_overlay_renders_typed_bridge(self):
        source = gen.render(dict(gen.EXPECTED), qualified_map())
        self.assertIn("_udeks_lifecycle_apply = $1c2e", source)
        self.assertIn("decsp2 = $8f94", source)
        self.assertIn(".exportzp ptr1", source)
        self.assertIn("__code_run__ = $cdbd", source.lower())

    def test_active_overlay_end_and_page_slack_are_required(self):
        with self.assertRaisesRegex(ValueError, "scheduler page"):
            gen.render(
                dict(gen.EXPECTED),
                qualified_map().replace("001FF9 0003FA", "001FFA 0003FB"),
            )
        with self.assertRaisesRegex(ValueError, "lifecycle handler"):
            gen.render(
                dict(gen.EXPECTED),
                qualified_map().replace("00C58B 00006F", "00CB00 0005E4"),
            )

    def test_missing_or_wrong_typed_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            gen.render(
                dict(gen.EXPECTED), qualified_map().replace("ptr1 00000E REZ\n", "")
            )
        with self.assertRaisesRegex(ValueError, "map type"):
            gen.render(
                dict(gen.EXPECTED), qualified_map().replace("sp 000006 REZ", "sp 000006 REA")
            )


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from placement_audit import (
    BOOT_GATEWAY_BASE,
    BOOT_GATEWAY_LIMIT,
    VIC_GATEWAY_BASE,
    VIC_GATEWAY_LARGEST,
    VIC_SHADOW_START,
    audit,
    parse_map,
    vic_bitmap_size,
)


FIXTURE = """\
Modules list:
-------------
alpha.o:
    CODE              Offs=000000  Size=000100  Align=00001  Fill=0000
    BSS               Offs=000000  Size=000010  Align=00001  Fill=0000
boot_console.o:
    CODE              Offs=000100  Size=000200  Align=00001  Fill=0000
probe.o:
    CODE              Offs=000300  Size=000040  Align=00001  Fill=0000

Segment list:
-------------
Name                   Start     End    Size  Align
----------------------------------------------------
STARTUP               002000  0020AD  0000AE  00001
CODE                  0020AE  0023FA  00034C  00001
BSS                   0023FB  00240A  000010  00001
VICSHADOW             00AF00  00CEFF  002000  00001
SYSCALLS              00CF00  00CFF8  0000F9  00001
"""


class PlacementAuditTests(unittest.TestCase):
    def test_parses_modules_and_segments(self):
        modules, segments = parse_map(FIXTURE)
        self.assertEqual(modules["alpha.o"], 0x110)
        self.assertEqual(modules["boot_console.o"], 0x200)
        names = [name for name, _, _, _ in segments]
        self.assertIn("VICSHADOW", names)
        self.assertIn("SYSCALLS", names)

    def test_audit_computes_the_reclaim_budget(self):
        result = audit(FIXTURE)
        self.assertEqual(result["data_end"], 0x240A)
        self.assertEqual(result["kernel_gap"], VIC_SHADOW_START - 0x240A)
        self.assertEqual(result["vic_shadow_padding"], 0x2000 - 8000)
        self.assertEqual(result["boot_only"]["boot_console.o"], 0x200)
        self.assertEqual(result["boot_only"]["probe.o"], 0x40)
        self.assertEqual(
            result["reclaim_total"],
            0x200 + 0x40 + (VIC_SHADOW_START - 0x240A) + 192,
        )
        self.assertEqual(
            result["boot_gateway_bytes"], BOOT_GATEWAY_LIMIT - BOOT_GATEWAY_BASE
        )
        self.assertEqual(
            result["vic_gateway_uncontested_bytes"],
            BOOT_GATEWAY_LIMIT - (VIC_GATEWAY_BASE + VIC_GATEWAY_LARGEST),
        )

    def test_fixture_is_missing_a_shadow_segment(self):
        with self.assertRaisesRegex(ValueError, "VICSHADOW"):
            audit(
                FIXTURE.replace("VICSHADOW             00AF00  00CEFF  002000", "")
            )


class PlacementContractTests(unittest.TestCase):
    def test_shadow_constants_match_the_header_and_config(self):
        self.assertEqual(vic_bitmap_size(), 8000)
        config = (ROOT / "cfg/8502-bootstrap.cfg").read_text(encoding="utf-8")
        match = re.search(
            r"VICSHADOW:\s+load = KERNEL.*?start = \$([0-9A-Fa-f]+)",
            config,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1), 16), VIC_SHADOW_START)

    def test_boot_gateway_page_is_below_the_task_loader(self):
        memory = (ROOT / "include/udeks/memory.h").read_text(encoding="utf-8")
        self.assertIn("UDEKS_BOOT_GATEWAY_BASE       0xF700u", memory)
        self.assertIn("UDEKS_TASK_STACK_TOP            0xF7F0u", (
            ROOT / "include/udeks/task.h"
        ).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

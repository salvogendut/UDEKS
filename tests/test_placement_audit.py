# SPDX-License-Identifier: GPL-3.0-or-later

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from placement_audit import (
    COMMON_GATEWAY,
    TASK_GATE_BASE,
    TASK_GATE_END,
    VIC_SHADOW_START,
    audit,
    parse_map,
    verify,
    vic_bitmap_size,
)


FIXTURE = """\
Modules list:
-------------
crt0.o:
    ZEROPAGE          Offs=000000  Size=000002  Align=00001  Fill=0000
    STARTUP           Offs=000000  Size=0000AE  Align=00001  Fill=0000
boot_console.o:
    CODE              Offs=000000  Size=000200  Align=00001  Fill=0000
probe.o:
    CODE              Offs=000200  Size=000040  Align=00001  Fill=0000
hardware_capability.o:
    CODE              Offs=000240  Size=0003C8  Align=00001  Fill=0000
alpha.o:
    CODE              Offs=000608  Size=000100  Align=00001  Fill=0000
    BSS               Offs=000000  Size=000010  Align=00001  Fill=0000

Segment list:
-------------
Name                   Start     End    Size  Align
----------------------------------------------------
STARTUP               002000  0020AD  0000AE  00001
CODE                  0020AE  0023FA  00034C  00001
BSS                   0023FB  00240A  000010  00001
VICSHADOW             00AF00  00CEFF  002000  00001
SYSCALLS              00CF00  00CFF8  0000F9  00001
TASKGATE              00FF05  00FFC4  0000C0  00001

"""


OBJECT_DUMP = """\
      Name:       "_udeks_vic_gateway_size_vic"
      Value:               0x000000FE  (254)
      Name:    "_udeks_vic_gateway_size_sprite"
      Value:               0x0000002E  (46)
      Name:      "_udeks_vic_gateway_size_page"
      Value:               0x00000044  (68)
      Name:   "_udeks_vic_gateway_size_outline"
      Value:               0x00000166  (358)
"""


class PlacementAuditTests(unittest.TestCase):
    def test_module_sizes_exclude_zero_page(self):
        modules, _ = parse_map(FIXTURE)
        from placement_audit import module_code_size

        self.assertEqual(modules["crt0.o"]["ZEROPAGE"], 2)
        self.assertEqual(module_code_size(modules["crt0.o"]), 0xAE)

    def test_audit_uses_inclusive_segment_ends(self):
        result = audit(FIXTURE, OBJECT_DUMP)
        self.assertEqual(result["data_end"], 0x240A)
        self.assertEqual(result["kernel_used"], 0x240A - 0x2000 + 1)
        self.assertEqual(result["kernel_gap"], VIC_SHADOW_START - 0x240B)
        self.assertEqual(result["vic_shadow_padding"], 0x2000 - 8000)
        self.assertEqual(result["boot_only"]["crt0.o"], 174)
        self.assertEqual(
            result["reclaim_total"],
            174 + 0x200 + 0x40 + 0x3C8
            + (VIC_SHADOW_START - 0x240B) + 192 + 0x400,
        )

    def test_gateway_sizes_come_from_the_assembled_object(self):
        result = audit(FIXTURE, OBJECT_DUMP)
        self.assertEqual(result["gateway_sizes"], [254, 46, 68, 358])
        self.assertEqual(result["gateway_total"], 358)
        self.assertEqual(result["gateway_end"], COMMON_GATEWAY + 358 - 1)
        self.assertEqual(result["gateway_end"], 0xF7EF)

    def test_boot_page_is_fully_overlapped(self):
        result = audit(FIXTURE, OBJECT_DUMP)
        self.assertEqual(result["uncontested_boot_page_bytes"], 0)
        self.assertIn("VIC common gateways", result["boot_page_overlaps"])
        self.assertIn("transient task stack", result["boot_page_overlaps"])

    def test_missing_object_dump_reports_unknown_gateways(self):
        result = audit(FIXTURE)
        self.assertIsNone(result["gateway_sizes"])
        self.assertIsNone(result["gateway_end"])
        self.assertNotIn("VIC common gateways", result["boot_page_overlaps"])

    def test_legacy_task_gate_is_read_from_the_map(self):
        result = audit(FIXTURE, OBJECT_DUMP)
        self.assertEqual(result["task_gate"]["base"], TASK_GATE_BASE)
        self.assertEqual(result["task_gate"]["end"], TASK_GATE_END)
        self.assertEqual(result["task_gate"]["size"], 192)

    def test_fixture_is_missing_a_shadow_segment(self):
        with self.assertRaisesRegex(ValueError, "VICSHADOW"):
            audit(
                FIXTURE.replace("VICSHADOW             00AF00  00CEFF  002000", "")
            )


class PlacementVerifyTests(unittest.TestCase):
    def test_valid_audit_has_no_failures(self):
        self.assertEqual(verify(audit(FIXTURE, OBJECT_DUMP)), [])

    def test_missing_measurements_fail(self):
        failures = verify(audit(FIXTURE))
        self.assertTrue(
            any("unavailable" in failure for failure in failures)
        )

    def test_changed_overlap_expectation_fails(self):
        result = audit(FIXTURE, OBJECT_DUMP)
        result["uncontested_boot_page_bytes"] = 8
        failures = verify(result)
        self.assertTrue(
            any("expectation changed" in failure for failure in failures)
        )

    def test_gateway_growth_beyond_the_baseline_fails(self):
        dump = OBJECT_DUMP.replace("0x00000166  (358)", "0x00000190  (400)")
        result = audit(FIXTURE, dump)
        failures = verify(result)
        self.assertEqual(result["gateway_end"], COMMON_GATEWAY + 400 - 1)
        self.assertTrue(any("baseline" in failure for failure in failures))
        self.assertTrue(any("beyond" in failure for failure in failures))
        self.assertTrue(any("$F800" in failure for failure in failures))

    def test_relocated_task_gate_fails(self):
        map_text = FIXTURE.replace(
            "TASKGATE              00FF05  00FFC4  0000C0  00001",
            "TASKGATE              00FE00  00FEBF  0000C0  00001",
        )
        failures = verify(audit(map_text, OBJECT_DUMP))
        self.assertTrue(
            any("TASKGATE moved" in failure for failure in failures)
        )

    def test_missing_task_gate_fails(self):
        map_text = FIXTURE.replace(
            "TASKGATE              00FF05  00FFC4  0000C0  00001\n", ""
        )
        failures = verify(audit(map_text, OBJECT_DUMP))
        self.assertTrue(
            any("missing" in failure for failure in failures)
        )

    def test_missing_overlap_names_fail(self):
        result = audit(FIXTURE, OBJECT_DUMP)
        result["boot_page_overlaps"] = []
        failures = verify(result)
        self.assertTrue(
            any("VIC common gateways" in failure for failure in failures)
        )
        self.assertTrue(
            any("transient task stack" in failure for failure in failures)
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

    def test_makefile_runs_the_real_audit_in_the_reference_container(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("placement-check", makefile)
        self.assertIn("tools/placement_audit.py --verify", makefile)

    def test_frozen_task_bank_entries_are_documented(self):
        placement = (ROOT / "docs/SCHEDULER-PLACEMENT.md").read_text(
            encoding="utf-8"
        )
        for entry in ("`$FF10`", "`$FF13`", "`$FF16`"):
            self.assertIn(entry, placement)

    def test_vic_source_exports_absolute_gateway_sizes(self):
        source = (ROOT / "src/8502/vic_graphics.s").read_text(encoding="utf-8")
        self.assertIn(
            "_udeks_vic_gateway_size_outline = outline_gateway_end-outline_gateway",
            source,
        )
        self.assertIn(
            ".export _udeks_vic_gateway_size_page, "
            "_udeks_vic_gateway_size_outline",
            source,
        )

    def test_transient_stack_and_loader_constants_match_sources(self):
        memory = (ROOT / "include/udeks/memory.h").read_text(encoding="utf-8")
        task = (ROOT / "include/udeks/task.h").read_text(encoding="utf-8")
        self.assertIn("UDEKS_BOOT_GATEWAY_BASE       0xF700u", memory)
        self.assertIn("UDEKS_TASK_STACK_TOP            0xF7F0u", task)
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text(
            encoding="utf-8"
        )
        self.assertIn("TASK_STACK_TOP          = $f7f0", stage1)
        self.assertIn("lda #<TASK_STACK_TOP", stage1)


if __name__ == "__main__":
    unittest.main()

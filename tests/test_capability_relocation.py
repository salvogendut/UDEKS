# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from boot_chain_decode import parse_result as parse_boot_chain  # noqa: E402
from capability_decode import parse_result as parse_capability  # noqa: E402

RAW = ROOT / "bench/results/2026-09-27-capability-relocation/raw"


class CapabilityRelocationContractTests(unittest.TestCase):
    def test_capability_is_a_separate_exact_size_image_at_slot_one(self):
        config = (ROOT / "cfg/8502-boot-capability.cfg").read_text(
            encoding="utf-8"
        )
        self.assertIn("APP: start = $0200, size = $0A00", config)
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn(
            "-o $(CAPABILITY_BIN) $(BUILD_8502)/hardware_capability.o",
            makefile,
        )
        self.assertEqual(
            makefile.count("$(BUILD_8502)/hardware_capability.o"), 5
        )

    def test_resident_descriptor_uses_fixed_entry_and_has_no_poll(self):
        descriptor = (ROOT / "src/services/capability/descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertIn(".addr $0200", descriptor)
        self.assertNotIn(".import _udeks_capability_start", descriptor)
        self.assertGreaterEqual(descriptor.count(".addr $0000"), 2)

    def test_installer_copies_exact_image_checks_sum_and_clears_bss(self):
        installer = (ROOT / "src/boot/capability-installer.s").read_text(
            encoding="utf-8"
        )
        self.assertIn("ldx #>CAPABILITY_IMAGE_SIZE", installer)
        self.assertIn("cpy #<CAPABILITY_IMAGE_SIZE", installer)
        self.assertIn("cmp #<CAPABILITY_IMAGE_CHECKSUM", installer)
        self.assertIn("cmp #>CAPABILITY_IMAGE_CHECKSUM", installer)
        self.assertIn("sta CAPABILITY_BSS", installer)
        self.assertIn("sta BOOT_CHAIN_FAILURE", installer)
        self.assertIn("sta BOOT_CHAIN_STATE", installer)

    def test_service_start_guard_precedes_any_descriptor_access(self):
        veneer = (ROOT / "src/8502/service_start.s").read_text(
            encoding="utf-8"
        )
        registry = (ROOT / "src/kernel/service_registry.c").read_text(
            encoding="utf-8"
        )
        self.assertIn(".export _udeks_service_start_all", veneer)
        self.assertIn("cmp #SERVICE_READY", veneer)
        self.assertIn("jmp _udeks_service_start_all_once", veneer)
        ready_path = veneer.split("cmp #SERVICE_READY", 1)[1]
        self.assertLess(ready_path.index("rts"), ready_path.index("start_services:"))
        self.assertIn(
            "unsigned char udeks_service_start_all_once(void)", registry
        )

    def test_stage1_calls_the_installer_before_final_crt0_install(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text(
            encoding="utf-8"
        )
        call = stage1.index("jsr CAPABILITY_INSTALLER")
        self.assertLess(call, stage1.index("jmp final_install", call))
        self.assertIn('.include "capability-delivery.inc"', stage1)


class CapabilityRelocationEvidenceTests(unittest.TestCase):
    def test_hcap_records_match_across_disk_formats_and_emulators(self):
        records = [
            (RAW / name).read_bytes()
            for name in (
                "vice-d71-hcap.bin", "vice-d64-hcap.bin", "1986-hcap.bin"
            )
        ]
        for record in records:
            parse_capability(record)
        self.assertEqual(records[0], records[1])
        self.assertEqual(records[0], records[2])

    def test_initial_slot_is_the_linked_image_plus_cleared_bss(self):
        expected = (RAW / "8502-capability.bin").read_bytes() + b"\x00"
        for name in (
            "vice-d71-slot1-at-start.bin",
            "vice-d64-slot1-at-start.bin",
            "1986-slot1-at-start.bin",
        ):
            self.assertEqual((RAW / name).read_bytes(), expected)

    def test_reentry_preserves_the_live_xclock_image(self):
        before = (RAW / "vice-d71-xclock-before-reentry.bin").read_bytes()
        after = (RAW / "vice-d71-xclock-after-reentry.bin").read_bytes()
        initial = (RAW / "vice-d71-slot1-at-start.bin").read_bytes()
        self.assertNotEqual(before, initial)
        self.assertEqual(after, before)

    def test_1986_native_boot_chain_is_complete(self):
        result = parse_boot_chain((RAW / "1986-boot-chain.bin").read_bytes())
        self.assertEqual(result["loader_state"], 2)
        self.assertEqual(result["blocks"], 212)


if __name__ == "__main__":
    unittest.main()

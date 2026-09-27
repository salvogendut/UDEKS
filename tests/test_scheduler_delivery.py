# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_d71 import scheduler_layout


RAW = ROOT / "bench/results/2026-09-26-scheduler-delivery/raw"
SCHEDULER_ADDRESS = 0x1C00
SCHEDULER_PAGE_SIZE = 0x0400


class SchedulerDeliveryEvidenceTests(unittest.TestCase):
    def test_d71_and_d64_install_the_same_scheduler_page(self):
        d71 = (RAW / "d71-installed.bin").read_bytes()
        d64 = (RAW / "d64-installed.bin").read_bytes()
        self.assertEqual(len(d71), SCHEDULER_PAGE_SIZE)
        self.assertEqual(d71, d64)

    def test_installed_page_matches_the_linked_scheduler_image(self):
        scheduler = (RAW / "udeks-scheduler.bin").read_bytes()
        d71 = (RAW / "d71-installed.bin").read_bytes()
        self.assertEqual(d71, scheduler.ljust(SCHEDULER_PAGE_SIZE, b"\x00"))
        self.assertEqual(
            (RAW / "1986-f9c6a24-installed.bin").read_bytes(), d71
        )

    def test_scheduler_entry_continues_through_the_kernel_vector(self):
        scheduler = (RAW / "udeks-scheduler.bin").read_bytes()
        self.assertEqual(scheduler[:3], b"\x4c\x00\x20")
        self.assertEqual(scheduler[3:7], b"SCHD")
        self.assertEqual(scheduler[7:9], b"\x00\x01")


class SchedulerDeliveryContractTests(unittest.TestCase):
    def test_current_scatter_ceiling_and_all_chunks_are_locked(self):
        _, chunks, ceiling = scheduler_layout(0xAC3E, 0x0B3D, 766)
        self.assertEqual(ceiling, 777)
        self.assertEqual(
            chunks,
            [
                (0x0B3E, 194),
                (0xAC3E, 155),
                (0xC409, 230),
                (0xC78A, 118),
                (0xCDF0, 16),
                (0xCEC0, 53),
            ],
        )
        with self.assertRaisesRegex(ValueError, "deliver at most 777"):
            scheduler_layout(0xAC3E, 0x0B3D, 778)

    def test_secondary_installer_runs_before_probe_and_page_copy_follows_crt0(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text(
            encoding="utf-8"
        )
        gather = stage1.index("jsr $ff05")
        probe = stage1.index("final_copy_probe_source:")
        install = stage1.index("scheduler_install:")
        self.assertLess(gather, probe)
        self.assertLess(probe, install)
        self.assertIn('.segment "SCHEDINSTALL"', stage1)
        self.assertIn("jmp $1c00", stage1)
        stage0 = (ROOT / "src/boot/stage0.s").read_text(encoding="utf-8")
        preload = (ROOT / "src/boot/stage1.s").read_text(encoding="utf-8")
        self.assertIn("jsr $1fbb", stage0)
        self.assertIn('.byte "SCHEDOVR"', preload)
        self.assertIn("jsr $ffd5", preload)

    def test_capability_staging_is_excluded_from_scheduler_chunks(self):
        _, chunks, ceiling = scheduler_layout(
            0xA895, 0x0B3D, 297, 967 + 102
        )
        self.assertEqual(ceiling, 645)
        self.assertEqual(
            chunks,
            [(0x0B3E, 194), (0xACC2, 23), (0xC409, 80)],
        )
        for start, length in chunks:
            self.assertTrue(start + length <= 0xA895 or start > 0xACC1)

    def test_capability_installs_before_crt0_clears_its_source(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text(
            encoding="utf-8"
        )
        call = stage1.index("jsr CAPABILITY_INSTALLER")
        final = stage1.index("jmp final_install", call)
        self.assertLess(call, final)
        self.assertIn("capability_install_failed:", stage1)

    def test_crt0_returns_to_the_fixed_scheduler_copier(self):
        crt0 = (ROOT / "src/8502/crt0.s").read_text(encoding="utf-8")
        self.assertIn("jmp $f7d8", crt0)

    def test_kernel_entry_vectors_are_pinned(self):
        entry = (ROOT / "src/8502/kernel_entry.s").read_text(
            encoding="utf-8"
        )
        self.assertIn("_kernel_main_entry = $2000", entry)
        self.assertIn("_boot_delivery_entry = $2003", entry)
        self.assertIn("_boot_delivery_gather = $a1e0", entry)

    def test_boot_delivery_uses_no_bss_or_cc65_state(self):
        delivery = (ROOT / "src/8502/boot_delivery.s").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('.segment "BSS"', delivery)
        self.assertIn('.segment "BOOTDELIVERY"', delivery)
        self.assertIn("SCATTER_MANIFEST = $acd9", delivery)
        self.assertIn("sta BOOT_CHAIN_FAILURE", delivery)
        self.assertIn("_boot_delivery_gather = $a1e0", delivery)
        config = (ROOT / "cfg/8502-boot-delivery.cfg").read_text(
            encoding="utf-8"
        )
        self.assertIn("DELIVERY: start = $A1E0, size = $010B", config)


if __name__ == "__main__":
    unittest.main()

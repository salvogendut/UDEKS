# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContextSwitchSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launcher = (
            ROOT / "bench/context-switch/launcher.s"
        ).read_text(encoding="utf-8").lower()
        cls.gateway = (
            ROOT / "bench/context-switch/gateway.s"
        ).read_text(encoding="utf-8").lower()
        cls.config = (
            ROOT / "cfg/8502-context-switch.cfg"
        ).read_text(encoding="utf-8").lower()
        cls.makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    def test_core_runs_from_common_ram(self):
        self.assertIn('.assert gateway_start = $f800', self.gateway)
        self.assertIn('.assert gateway_end - gateway_start <= $0700', self.gateway)
        self.assertIn("common: start = $f800, size = $0700", (
            ROOT / "cfg/8502-common-gateway.cfg"
        ).read_text(encoding="utf-8").lower())
        self.assertIn('main: start = $2800', self.config)

    def test_launcher_installs_the_core_and_result_header(self):
        self.assertIn(".incbin \"build/bench/context-switch/gateway.bin\"",
                      self.launcher)
        self.assertIn("result                  = $f180", self.launcher)
        self.assertIn("sta mmu_rcr", self.launcher)
        self.assertIn("sta mmu_pcr_kernel_io", self.launcher)
        self.assertIn("sta mmu_pcr_worker_io", self.launcher)

    def test_tasks_own_distinct_relocated_pages_and_profiles(self):
        for page in ("$80", "$81", "$82", "$83"):
            self.assertIn(f"lda #{page}", self.gateway)
        self.assertIn("sta mmu_page0_page", self.gateway)
        self.assertIn("sta mmu_page1_page", self.gateway)
        self.assertIn("profile_kernel_io       = 1", self.gateway)
        self.assertIn("profile_worker_io       = 3", self.gateway)
        self.assertIn("sta mmu_lcr_worker_io", self.gateway)
        self.assertIn("sta mmu_page0_bank", self.gateway)
        self.assertIn("sta mmu_page1_bank", self.gateway)

    def test_resume_uses_an_explicit_saved_program_counter(self):
        self.assertIn("jmp yield_core", self.gateway)
        self.assertIn("sta save_pc", self.gateway)
        self.assertIn("jmp (save_pc)", self.gateway)
        self.assertIn("ldx save_sp", self.gateway)
        self.assertIn("txs", self.gateway)

    def test_interrupt_path_reads_common_ram_and_acknowledges_cia(self):
        self.assertIn("irq_handler:", self.gateway)
        self.assertIn("inc irq_count", self.gateway)
        self.assertIn("lda cia1_icr", self.gateway)
        self.assertIn("rti", self.gateway)
        self.assertIn("cli", self.gateway)
        self.assertIn("sei", self.gateway)

    def test_makefile_builds_the_standalone_prg(self):
        self.assertIn("bench-context-switch", self.makefile)
        self.assertIn(
            "tools/bin_to_prg.py --load-address 0x2800", self.makefile
        )

    def test_decoder_reads_the_same_result_base(self):
        decoder = (
            ROOT / "tools/context_switch_decode.py"
        ).read_text(encoding="utf-8")
        self.assertIn("RESULT_BASE = 0xF180", decoder)
        self.assertIn("RESULT_SIZE = 32", decoder)


if __name__ == "__main__":
    unittest.main()

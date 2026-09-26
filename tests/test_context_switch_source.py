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

    def test_each_task_has_its_own_context_record(self):
        for label in (
            "a_ctx_a:", "a_ctx_x:", "a_ctx_y:", "a_ctx_p:", "a_ctx_sp:",
            "a_ctx_pc:", "b_ctx_a:", "b_ctx_x:", "b_ctx_y:", "b_ctx_p:",
            "b_ctx_sp:", "b_ctx_pc:",
        ):
            self.assertIn(label, self.gateway)
        self.assertIn("sta a_ctx_a", self.gateway)
        self.assertIn("sta b_ctx_a", self.gateway)
        self.assertIn("jmp (a_ctx_pc)", self.gateway)
        self.assertIn("jmp (b_ctx_pc)", self.gateway)
        self.assertIn("task_a_resume", self.gateway)
        self.assertIn("task_b_resume", self.gateway)

    def test_tasks_use_distinct_register_stack_and_marker_patterns(self):
        self.assertIn("a_stack_init            = $ff", self.gateway)
        self.assertIn("b_stack_init            = $f5", self.gateway)
        for constant in (
            "a_seed_a", "b_seed_a", "a_ytag", "b_ytag", "a_mark_low",
            "a_mark_high", "b_mark_low", "b_mark_high",
        ):
            self.assertIn(constant, self.gateway)

    def test_stack_sentinels_live_in_the_active_stack_region(self):
        self.assertIn("stack_page_base+1,x", self.gateway)
        self.assertIn("stack_page_base+2,x", self.gateway)
        self.assertIn("lda #a_mark_low\n        pha", self.gateway)
        self.assertIn("lda #b_mark_low\n        pha", self.gateway)
        self.assertIn("task_a_resume:\n        jmp task_a_entry", self.gateway)
        self.assertIn("task_b_resume:\n        jmp task_b_entry", self.gateway)
        self.assertIn("adc #$02\n        sta a_ctx_sp", self.gateway)
        self.assertIn("adc #$02\n        sta b_ctx_sp", self.gateway)

    def test_interrupt_handler_preserves_a_x_and_y(self):
        handler = self.gateway.split("irq_handler:", 1)[1].split(
            "current:", 1)[0]
        for instruction in (
            "pha", "txa", "tya", "pla", "tay", "tax", "rti", "lda cia1_icr"
        ):
            self.assertIn(instruction, handler)
        for name in ("boundary_irqs", "body_irqs", "window_flag"):
            self.assertIn(name, handler)

    def test_switch_boundary_window_is_marked_and_counted(self):
        self.assertIn("sta window_flag", self.gateway)
        self.assertIn("lda window_flag", self.gateway)
        self.assertIn("inc boundary_irqs", self.gateway)
        self.assertIn("inc body_irqs", self.gateway)
        self.assertIn("result_boundary_irq     = result + 22", self.gateway)
        self.assertIn("result_body_irq         = result + 23", self.gateway)

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

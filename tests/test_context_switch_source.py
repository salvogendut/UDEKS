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
        self.assertIn("jmp (a_ctx_pc)", self.gateway)
        self.assertIn("jmp (b_ctx_pc)", self.gateway)

    def test_each_task_has_two_distinct_resume_entry_points(self):
        for label in (
            "task_a_resume0:", "task_a_resume1:",
            "task_b_resume0:", "task_b_resume1:",
        ):
            self.assertIn(label, self.gateway)
        for constant in (
            "resume_a_even", "resume_a_odd", "resume_b_even", "resume_b_odd",
        ):
            self.assertIn(constant, self.gateway)
        self.assertIn("zp_resume_seen", self.gateway)

    def test_status_is_captured_before_flags_change_and_restored_last(self):
        yield_core = self.gateway.split("yield_core:", 1)[1].split(
            "yield_validate_a:", 1)[0]
        capture = yield_core.index("php")
        self.assertLess(capture, yield_core.index("sei"))
        self.assertLess(capture, yield_core.index("sta tmp_p"))
        dispatch = self.gateway.split("dispatch_task_a_ready:", 1)[1].split(
            "dispatch_task_b:", 1)[0]
        for register_load in ("lda a_ctx_p\n",):
            self.assertIn(register_load, dispatch)
        self.assertLess(
            dispatch.index("ldy a_ctx_y"),
            dispatch.index("plp"),
        )
        self.assertLess(dispatch.index("plp"), dispatch.index("jmp (a_ctx_pc)"))

    def test_validation_uses_independent_expectations(self):
        for token in (
            "a_last_p", "b_last_p", "p_mask", "zp_seen_p",
            "a_sp_odd", "a_sp_even", "b_sp_odd", "b_sp_even",
            "a_pad", "b_pad",
        ):
            self.assertIn(token, self.gateway)
        # Restored A is checked against a step-derived formula, not a record.
        self.assertIn("sbc #$01\n        clc\n        adc #a_atag", self.gateway)
        self.assertIn("sbc #$01\n        clc\n        adc #b_atag", self.gateway)

    def test_stack_sentinels_live_in_the_active_stack_region(self):
        self.assertIn("stack_page_base+1,x", self.gateway)
        self.assertIn("stack_page_base+2,x", self.gateway)
        self.assertIn("lda #a_mark_low\n        pha", self.gateway)
        self.assertIn("lda #b_mark_low\n        pha", self.gateway)

    def test_interrupt_handler_preserves_a_x_y_and_counts_sixteen_bits(self):
        handler = self.gateway.split("irq_handler:", 1)[1].split(
            "current:", 1)[0]
        for instruction in ("pha", "txa", "tya", "pla", "tay", "tax", "rti"):
            self.assertIn(instruction, handler)
        for name in (
            "boundary_lo", "boundary_hi", "body_lo", "body_hi",
            "window_flag",
        ):
            self.assertIn(name, handler)

    def test_result_publishes_sixteen_bit_interrupt_counters(self):
        self.assertIn("result_boundary_lo      = result + 22", self.gateway)
        self.assertIn("result_body_lo          = result + 23", self.gateway)
        self.assertIn("result_boundary_hi      = result + 24", self.gateway)
        self.assertIn("result_body_hi          = result + 25", self.gateway)

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

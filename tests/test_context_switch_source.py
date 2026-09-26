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
        self.assertIn('.assert gateway_start = $f400', self.gateway)
        self.assertIn('.assert gateway_end - gateway_start <= $0b00', self.gateway)
        self.assertIn("common: start = $f400, size = $0b00", (
            ROOT / "cfg/8502-context-switch-gateway.cfg"
        ).read_text(encoding="utf-8").lower())
        self.assertIn('main: start = $2800', self.config)
        self.assertIn("gateway                 = $f400", self.launcher)

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
            "task_a_first:", "task_a_resume0:", "task_a_resume1:",
            "task_a_resume_check:", "task_b_first:", "task_b_resume0:",
            "task_b_resume1:", "task_b_resume_check:",
        ):
            self.assertIn(label, self.gateway)
        self.assertIn("lda #<task_a_first", self.gateway)
        self.assertIn("lda #<task_b_first", self.gateway)
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
            "tmp_pad", "a_pad", "b_pad",
        ):
            self.assertIn(token, self.gateway)
        # Restored A is checked against a step-derived formula, not a record.
        self.assertIn("sbc #$01\n        clc\n        adc #a_atag", self.gateway)
        self.assertIn("sbc #$01\n        clc\n        adc #b_atag", self.gateway)
        # The live stack pointer varies with a step-derived pad.
        self.assertIn("and #$03\n        asl a\n        sta tmp_pad", self.gateway)
        self.assertIn("clc\n        adc #$02\n        sta tmp_pad", self.gateway)
        self.assertIn("txa\n        clc\n        adc tmp_pad\n        tax\n        txs", self.gateway)

    def test_resume_verifies_and_pops_the_surviving_frame(self):
        self.assertNotIn("adc tmp_pad\n        sta a_ctx_sp", self.gateway)
        self.assertNotIn("adc tmp_pad\n        sta b_ctx_sp", self.gateway)
        self.assertIn("lda tmp_sp\n        sta a_ctx_sp", self.gateway)
        self.assertIn("lda tmp_sp\n        sta b_ctx_sp", self.gateway)
        for label in ("task_a_resume_check:", "task_b_resume_check:"):
            check = self.gateway.split(label, 1)[1].split("jmp task_", 1)[0]
            self.assertIn("cld\n        tsx", check)
            self.assertIn("cmp zp_step", check)
            self.assertIn("lda #17", check)
            self.assertIn("jmp fail_canary", check)
            self.assertIn("adc tmp_pad", check)
            self.assertIn("txs", check)

    def test_restored_decimal_flag_drives_per_task_arithmetic(self):
        self.assertIn("zp_dec_result", self.gateway)
        self.assertIn("dec_a                   = $42", self.gateway)
        self.assertIn("dec_b                   = $3c", self.gateway)
        self.assertIn("require_imm dec_a, 16", self.gateway)
        self.assertIn("require_imm dec_b, 16", self.gateway)
        self.assertIn("sec\n        sed\n        jmp yield_core", self.gateway)
        self.assertIn("sec\n        cld\n        jmp yield_core", self.gateway)
        a_replay = self.gateway.split("yield_validate_a:", 1)[1].split(
            "yield_validate_b:", 1)[0]
        b_replay = self.gateway.split("yield_validate_b:", 1)[1].split(
            "yield_accept:", 1)[0]
        self.assertIn("sec\n        sed\n        php", a_replay)
        self.assertIn("sec\n        cld\n        php", b_replay)

    def test_stack_sentinels_live_in_the_active_stack_region(self):
        self.assertIn("stack_page_base+1,x", self.gateway)
        self.assertIn("stack_page_base+2,x", self.gateway)
        # The marker low byte is the current step, so stale stack data fails.
        self.assertIn("lda zp_step\n        pha", self.gateway)
        self.assertIn("cmp zp_step", self.gateway)
        self.assertIn("lda #a_mark_high\n        pha", self.gateway)
        self.assertIn("lda #b_mark_high\n        pha", self.gateway)
        self.assertIn("pad_loop_a:", self.gateway)
        self.assertIn("pad_loop_b:", self.gateway)

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

    def test_result_is_printed_to_both_screens_before_halt(self):
        self.assertIn("readout:", self.gateway)
        self.assertIn("readout_hex_vic:", self.gateway)
        self.assertIn("readout_hex_vdc:", self.gateway)
        self.assertIn("sta vdc_address", self.gateway)
        self.assertIn("sta vdc_data", self.gateway)
        # Success and failure both jump to the readout.
        self.assertEqual(self.gateway.count("jmp readout\n"), 2)

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

# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TaskBankGatewayTests(unittest.TestCase):
    def test_cc65_stack_pointer_uses_none_runtime_zero_page_location(self):
        gate = (ROOT / "src/8502/task_bank_gateway.s").read_text().lower()
        loader = (ROOT / "src/boot/stage1-gateway.s").read_text().lower()

        self.assertIn("cc65_sp_index           = $00", gate)
        self.assertIn("resident_cc65_sp        = $06", loader)
        self.assertIn("user_cc65_sp            = $02", loader)

    def test_fixed_common_ram_contract_matches_public_header(self):
        config = (ROOT / "cfg/8502-bootstrap.cfg").read_text().lower()
        header = (ROOT / "include/udeks/task_bank.h").read_text().lower()
        gate = (ROOT / "src/8502/task_bank_gateway.s").read_text().lower()

        self.assertIn("taskgate: start = $ff05, size = $00cb", config)
        self.assertIn("udeks_task_bank_gate_base         0xff05u", header)
        self.assertIn("udeks_task_bank_reset             0xff10u", header)
        self.assertIn("udeks_task_bank_poll              0xff13u", header)
        self.assertIn("udeks_task_bank_request           0xff16u", header)
        self.assertIn(".assert * = $ff10", gate)
        self.assertIn(".assert task_gate_end <= $ffd0", gate)

    def test_task_context_is_bank_private(self):
        header = (ROOT / "include/udeks/task_bank.h").read_text().lower()
        gate = (ROOT / "src/8502/task_bank_gateway.s").read_text().lower()

        self.assertIn("udeks_task_bank_context           0xe2e2u", header)
        self.assertIn("task_context            = $e2e2", gate)
        self.assertIn("sta task_context,x", gate)
        self.assertIn("lda task_context,x", gate)
        self.assertNotIn('.segment "bss"', gate)

    def test_poll_masks_interrupts_and_restores_kernel_map(self):
        gate = (ROOT / "src/8502/task_bank_gateway.s").read_text().lower()

        poll = gate.split("task_enter:", 1)[1].split("task_gate_end:", 1)[0]
        for instruction in (
            "php",
            "sei",
            "sta mmu_lcr_worker_flat",
            "jsr task_entry",
            "sta mmu_lcr_kernel_io",
            "jsr task_request_dispatch",
            "plp",
        ):
            self.assertIn(instruction, poll)

    def test_stage1_installs_exact_reserved_gateway_size(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text().lower()

        self.assertIn("lda $ce00,y", stage1)
        self.assertIn("sta $ff05,y", stage1)
        self.assertIn("cpy #$cb", stage1)

    def test_stage1_relocates_bootfs_and_installs_runtime_loader(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text().lower()

        self.assertIn("lda $2300,y", stage1)
        self.assertIn("bootfs_destination:\n        sta $0300,y", stage1)
        self.assertIn("lda #$23\n        sta bootfs_source+2", stage1)
        self.assertIn("lda #$a0\n        sta bootfs_destination+2", stage1)
        self.assertIn("ldx #$1d", stage1)
        self.assertIn("lda $af00,y", stage1)
        self.assertIn("sta $bd00,y", stage1)
        self.assertIn("ldx #$14", stage1)
        self.assertIn("lda $bfbb,y", stage1)
        self.assertIn("sta $e300,y", stage1)
        self.assertNotIn("lda $0c2a", stage1)
        self.assertIn("task_persistent_loader_entry:", stage1)
        self.assertIn("sta persistent_slot", stage1)
        self.assertIn("lda $c300,y", stage1)
        self.assertIn("sta $f800,y", stage1)
        self.assertIn("sta $f900,y\n        iny\n        cpy #$09", stage1)
        self.assertNotIn("final_clear_vic_shadow", stage1)
        self.assertIn("lda $c500,y", stage1)
        self.assertIn("sta $4000,y\n        iny\n        bne backup_service_page", stage1)
        self.assertIn("bootfs_base             = $a000", stage1)
        self.assertIn("task_managed_loader_entry:", stage1)

    def test_runtime_loader_is_installed_from_protected_final_page(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text().lower()
        protected, main = stage1.split('.segment "code"', 1)

        self.assertIn('.segment "final"', protected)
        self.assertIn("final_copy_task_loader_byte:", protected)
        self.assertIn("sta $f910,y", protected)
        self.assertNotIn("copy_task_loader_byte:", main)

    def test_task_loader_compares_bootfs_names_from_common_ram(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text().lower()
        lookup = stage1.split("task_find_file:", 1)[1].split(
            "task_file_found:", 1
        )[0]

        self.assertIn("sta task_header,y", lookup)
        self.assertIn("lda task_header,y", lookup)
        self.assertIn("cmp bootfs_base+$18,y", lookup)
        self.assertIn("sta task_entry_length_load+1", lookup)
        self.assertIn("sta task_entry_length_load+2", lookup)
        self.assertEqual(lookup.count("sta task_entry_length_load+1"), 2)
        self.assertEqual(lookup.count("sta task_entry_length_load+2"), 2)
        self.assertIn("sta task_argv_pointer_high_load+1", lookup)
        self.assertIn("sta task_argv_pointer_high_load+2", lookup)
        self.assertIn("tya\n        sta task_name_length", lookup)
        self.assertNotIn("task_command_compare_load", lookup)

        validation = stage1.split("task_fetch_header:", 1)[1].split(
            "task_check_entry:", 1
        )[0]
        self.assertIn("sta task_allocation_lo", validation)
        self.assertIn("sta task_allocation_hi", validation)
        self.assertIn("cmp task_file_size_lo", validation)
        self.assertIn("cmp task_file_size_hi", validation)
        self.assertIn("cmp #$0a", validation)

    def test_transient_slot_is_saved_even_while_xclock_is_active(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text().lower()

        self.assertNotIn("xclock_state", stage1)
        self.assertNotIn("xclock_running", stage1)
        self.assertIn("task_save_foreground:", stage1)
        self.assertIn("task_restore_page:", stage1)


if __name__ == "__main__":
    unittest.main()

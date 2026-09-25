# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TaskBankGatewayTests(unittest.TestCase):
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

    def test_stage1_relocates_bootfs_and_installs_persistent_task(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text().lower()

        self.assertIn("lda $2c00,y", stage1)
        self.assertIn("sta $0c00,y", stage1)
        self.assertIn("lda $c300,y", stage1)
        self.assertIn("sta $9000,y", stage1)
        self.assertIn("bootfs_base             = $0c00", stage1)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BootCrt0ConfigTests(unittest.TestCase):
    def test_bootcrt_area_is_the_stage1_page(self):
        config = (ROOT / "cfg/8502-bootstrap.cfg").read_text(encoding="utf-8")
        self.assertIn(
            "BOOTCRT: start = $1C00, size = $0100, type = ro,\n"
            '             file = "build/boot/8502-crt0.bin", fill = yes;',
            config,
        )
        self.assertIn("STARTUP:  load = BOOTCRT, type = ro;", config)

    def test_crt0_runs_from_scratch_and_jumps_to_the_core(self):
        crt0 = (ROOT / "src/8502/crt0.s").read_text(encoding="utf-8")
        self.assertIn(".import __BSS_RUN__, __BSS_SIZE__", crt0)
        self.assertIn(".import __VICSHADOW_RUN__, __VICSHADOW_SIZE__", crt0)
        self.assertIn("CLEAR_POINTER = $f8", crt0)
        self.assertIn("jmp _kernel_main", crt0)
        self.assertNotIn('jsr _kernel_main', crt0)
        self.assertNotIn('.segment "ZEROPAGE"', crt0)

    def test_stage1_copies_crt0_over_its_own_dead_page(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text(
            encoding="utf-8"
        )
        self.assertIn("final_copy_crt0_source:", stage1)
        self.assertIn("lda $ae00,y", stage1)
        self.assertIn("sta $1c00,y", stage1)
        self.assertIn("jmp $1c00", stage1)
        self.assertNotIn("jmp $2000", stage1)


class ZeroPageAbiTests(unittest.TestCase):
    def test_resident_and_app_zero_page_layouts_shift_together(self):
        loader = (ROOT / "src/boot/stage1-gateway.s").read_text(
            encoding="utf-8"
        )
        self.assertIn("RESIDENT_CC65_SP        = $04", loader)
        self.assertIn("USER_CC65_SP            = $02", loader)
        imports = (ROOT / "user/lib/app_imports.s").read_text(encoding="utf-8")
        for name, address in (
            ("sp", "04"),
            ("sreg", "06"),
            ("regsave", "08"),
            ("ptr1", "0c"),
            ("ptr2", "0e"),
            ("ptr3", "10"),
            ("ptr4", "12"),
            ("tmp1", "14"),
            ("tmp2", "15"),
            ("tmp3", "16"),
            ("tmp4", "17"),
            ("regbank", "18"),
        ):
            self.assertTrue(
                re.search(rf"^{name}\s+= \${address}$", imports, re.MULTILINE),
                f"{name} is not at ${address}",
            )


class BootCrt0BuildTests(unittest.TestCase):
    def test_kernel_and_crt0_share_one_linker_invocation(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("$(KERNEL_BIN) $(CRT0_BIN) &:", makefile)
        self.assertIn(
            "$(CL65) -t none --cpu 6502 $(LDFLAGS_8502) -o $(KERNEL_BIN) \\",
            makefile,
        )

    def test_boot_image_stages_crt0_and_prg_loads_from_its_page(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("--crt0 $(CRT0_BIN)", makefile)
        self.assertIn("tools/join_boot_crt0.py", makefile)
        self.assertIn("--load-address 0x1C00", makefile)


if __name__ == "__main__":
    unittest.main()

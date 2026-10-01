# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gen_boot_console_imports as gen  # noqa: E402


class BootConsoleRelocationContractTests(unittest.TestCase):
    def test_image_occupies_upper_slot_two_without_bss(self):
        config = (ROOT / "cfg/8502-boot-console.cfg").read_text(
            encoding="utf-8"
        )
        self.assertIn("APP: start = $1600, size = $0600", config)
        self.assertEqual(gen.DESTINATION, 0x1600)
        self.assertEqual(gen.IMAGE_SIZE, 1450)
        self.assertEqual(gen.CODE_SIZE + gen.RODATA_SIZE, gen.IMAGE_SIZE)

    def test_resident_entry_is_an_absolute_binding(self):
        entry = (ROOT / "src/8502/boot_console_entry.s").read_text(
            encoding="utf-8"
        )
        self.assertIn("_udeks_boot_console_build = $1600", entry)
        self.assertNotIn('.segment "CODE"', entry)

    def test_private_bridge_locks_entry_layout_and_zero_page_types(self):
        source = gen.render_bridge(
            [("absolute", "02", 0x2345), ("sp", "01", 0x0006)]
        )
        self.assertIn(".export absolute\nabsolute = $2345", source)
        self.assertIn(".exportzp sp\nsp = $0006", source)
        self.assertIn("_udeks_boot_console_build = $1600", source)
        self.assertIn("__CODE_SIZE__ = $03ab", source)
        self.assertIn("__RODATA_SIZE__ = $01ff", source)
        self.assertIn("__BSS_SIZE__ = $0000", source)

    def test_installer_copies_exact_image_and_checks_sum(self):
        installer = (ROOT / "src/boot/boot-console-installer.s").read_text(
            encoding="utf-8"
        )
        self.assertIn("ldx #>BOOT_CONSOLE_IMAGE_SIZE", installer)
        self.assertIn("cpy #<BOOT_CONSOLE_IMAGE_SIZE", installer)
        self.assertIn("cmp #<BOOT_CONSOLE_IMAGE_CHECKSUM", installer)
        self.assertIn("cmp #>BOOT_CONSOLE_IMAGE_CHECKSUM", installer)
        self.assertIn("sta BOOT_CHAIN_FAILURE", installer)
        self.assertIn("sta BOOT_CHAIN_STATE", installer)
        self.assertIn("boot_console_installer = $0b50", installer)

    def test_installer_checksum_covers_the_activation_image(self):
        generator = (ROOT / "tools/gen_boot_console_imports.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("installed_image = image + activation", generator)
        self.assertIn("checksum = sum(installed_image)", generator)
        self.assertIn("TASK_SWITCH_ACTIVATION_DESTINATION", generator)

    def test_stage1_installs_console_before_probe_overwrites_installer(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text(
            encoding="utf-8"
        )
        capability = stage1.index("jsr CAPABILITY_INSTALLER")
        console = stage1.index("jsr $0b50", capability)
        final = stage1.index("jmp final_install", console)
        install = stage1.index("jsr $ff05")
        probe = stage1.index("final_copy_probe_source:", install)
        self.assertLess(capability, console)
        self.assertLess(console, final)
        self.assertLess(install, probe)

    def test_resident_links_use_binding_not_console_object(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        normal = makefile.split(
            "$(KERNEL_BIN) $(CRT0_BIN) $(PROBE_BIN) $(KERNEL_MAP) $(BUILD_8502)/banked-graphics.bin &:", 1
        )[1].split("$(SCHEDULER_BIN):", 1)[0]
        panic = makefile.split(
            "$(PANIC_PROBE_KERNEL_BIN) $(PANIC_PROBE_CRT0_BIN)", 1
        )[1].split("$(KERNEL_DIRECT_BIN):", 1)[0]
        for link in (normal, panic):
            self.assertIn("$(BUILD_8502)/boot_console_entry.o", link)
            self.assertNotIn("$(BUILD_8502)/boot_console.o", link)


if __name__ == "__main__":
    unittest.main()

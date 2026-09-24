# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FramebufferBoundaryTests(unittest.TestCase):
    def test_c_service_uses_bounded_vdc_transport(self):
        source = (ROOT / "src/services/framebuffer/vdc_framebuffer.c").read_text(
            encoding="utf-8"
        ).lower()
        self.assertNotIn("0xd600", source)
        self.assertNotIn("0xd601", source)
        self.assertIn('"udeks/vdc.h"', source)

    def test_service_snapshots_complete_register_file(self):
        source = (ROOT / "src/services/framebuffer/vdc_framebuffer.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("#define VDC_REGISTER_COUNT          37u", source)
        self.assertIn("snapshot_registers()", source)
        self.assertIn("restore_display_state()", source)

    def test_service_is_optional_and_not_in_default_boot_registry(self):
        source = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        descriptor = (
            ROOT / "src/services/framebuffer/descriptor.s"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_udeks_framebuffer_service_descriptor", source)
        self.assertIn("_udeks_framebuffer_service_descriptor", descriptor)
        self.assertIn(".byte $0c", source)

        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        production_link = makefile.split("$(KERNEL_BIN):", 1)[1].split(
            "$(PANIC_PROBE_KERNEL_BIN):", 1
        )[0]
        self.assertNotIn("vdc_framebuffer.o", production_link)
        self.assertNotIn("framebuffer_surface.o", production_link)

    def test_linked_assets_have_exact_sizes(self):
        source = (ROOT / "src/assets/vdc_splash.s").read_text(encoding="utf-8")
        self.assertIn('.incbin "build/assets/udekspipe-64.vdc"', source)
        self.assertIn("= 512, error", source)
        self.assertIn('.incbin "build/assets/udekusu-64.vdc"', source)
        self.assertIn("= 168, error", source)

    def test_hardware_panel_consumes_capability_record(self):
        source = (ROOT / "src/services/framebuffer/vdc_framebuffer.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("UDEKS_CAPABILITY_STATUS_BASE", source)
        self.assertIn("compose_boot_console()", source)
        self.assertIn("udeks_boot_console_build()", source)
        self.assertNotIn("udeks_probe_", source)


if __name__ == "__main__":
    unittest.main()

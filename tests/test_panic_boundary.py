# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PanicBoundaryTests(unittest.TestCase):
    def test_panic_path_has_no_external_runtime_dependency(self):
        source = (ROOT / "src/8502/panic.s").read_text(encoding="utf-8")
        self.assertNotIn(".import", source)
        self.assertIn("_udeks_panic:", source)
        self.assertIn("panic_wait_ready:", source)
        self.assertIn("jmp halt", source)

    def test_kernel_escalates_registry_failure(self):
        source = (ROOT / "src/8502/kernel.c").read_text(encoding="utf-8")
        self.assertIn("startup_result = udeks_service_start_all()", source)
        self.assertIn("udeks_panic(", source)

    def test_probe_corrupts_only_descriptor_magic_at_source_level(self):
        source = (ROOT / "src/services/console/descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertIn(".ifdef UDEKS_FAULT_SERVICE_MAGIC", source)
        self.assertIn(".byte 'X', 'S', 'V', 'C'", source)
        self.assertIn(".byte 'U', 'S', 'V', 'C'", source)


if __name__ == "__main__":
    unittest.main()

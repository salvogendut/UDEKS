# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ServiceAbiTests(unittest.TestCase):
    def test_descriptor_is_explicit_and_fixed_size(self):
        descriptor = (ROOT / "src/services/console/descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertIn(".byte 'U', 'S', 'V', 'C'", descriptor)
        self.assertIn(".byte $00, $01", descriptor)
        self.assertIn("descriptor_end - _udeks_console_service_descriptor", descriptor)
        self.assertIn('= $10, error, "service descriptor size drift"', descriptor)

    def test_kernel_depends_only_on_registry_entry(self):
        kernel = (ROOT / "src/8502/kernel.c").read_text(encoding="utf-8")
        registry = (ROOT / "src/kernel/service_registry.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("udeks_service_start_all()", kernel)
        self.assertNotIn("console", kernel.lower())
        self.assertNotIn("console", registry.lower())

    def test_image_table_is_separate_from_registry(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        self.assertIn("_udeks_console_service_descriptor", table)
        self.assertIn("_udeks_service_count", table)


if __name__ == "__main__":
    unittest.main()

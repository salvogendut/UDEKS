# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VdcBoundaryTests(unittest.TestCase):
    def test_only_assembly_transport_names_mapped_vdc_ports(self):
        transport = (ROOT / "src/8502/vdc.s").read_text(encoding="utf-8").lower()
        service = (ROOT / "src/services/console/vdc_console.c").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("$d600", transport)
        self.assertIn("$d601", transport)
        self.assertNotIn("0xd600", service)
        self.assertNotIn("0xd601", service)
        self.assertIn('"udeks/vdc.h"', service)

    def test_transport_ready_wait_is_bounded(self):
        transport = (ROOT / "src/8502/vdc.s").read_text(encoding="utf-8")
        self.assertIn("inx", transport)
        self.assertIn("iny", transport)
        self.assertIn("VDC_TIMEOUT", transport)


if __name__ == "__main__":
    unittest.main()

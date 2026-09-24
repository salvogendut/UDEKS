# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CapabilityBoundaryTests(unittest.TestCase):
    def test_c_service_uses_bounded_transport(self):
        source = (ROOT / "src/services/capability/hardware.c").read_text(
            encoding="utf-8"
        ).lower()
        for address in ("0xd011", "0xd012", "0xd600", "0xde00", "0xdf00"):
            self.assertNotIn(address, source)
        self.assertIn('"udeks/vdc.h"', source)
        self.assertIn("udeks_probe_video_standard()", source)

    def test_probe_assembly_bounds_raster_and_vdc_waits(self):
        source = (ROOT / "src/8502/probe.s").read_text(encoding="utf-8")
        self.assertIn("scan_high_rasters:", source)
        self.assertIn("vdc_wait:", source)
        self.assertGreaterEqual(source.count("iny"), 4)

    def test_capability_service_precedes_console(self):
        source = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        capability = source.index(".addr _udeks_capability_service_descriptor")
        console = source.index(".addr _udeks_console_service_descriptor")
        self.assertLess(capability, console)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClockSourceTests(unittest.TestCase):
    def test_clock_follows_capability_and_precedes_displays(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        capability = table.index("_udeks_capability_service_descriptor")
        clock = table.index("_udeks_clock_service_descriptor", capability)
        console = table.index("_udeks_console_service_descriptor", clock)
        framebuffer = table.index("_udeks_framebuffer_service_descriptor", console)
        self.assertLess(capability, clock)
        self.assertLess(clock, console)
        self.assertLess(console, framebuffer)
        self.assertIn(".byte $06", table)

    def test_transition_blanks_vic_and_selects_fast_clock(self):
        source = (ROOT / "src/8502/clock.s").read_text(encoding="utf-8")
        self.assertIn("VIC_CONTROL_1           = $d011", source)
        self.assertIn("VIC_CLOCK               = $d030", source)
        self.assertIn("and #$ef", source)
        self.assertIn("and #$fd", source)
        self.assertIn("ora #$01", source)
        self.assertIn("cmp #$01", source)

    def test_clock_waits_for_capability_record(self):
        source = (ROOT / "src/8502/clock.s").read_text(encoding="utf-8")
        self.assertIn("CAPABILITY_STATE        = $f0c5", source)
        self.assertIn("cmp #$02", source)


if __name__ == "__main__":
    unittest.main()

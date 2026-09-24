# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClockSourceTests(unittest.TestCase):
    def test_fast_clock_is_optional_in_the_text_console_boot(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        capability = table.index("_udeks_capability_service_descriptor")
        console = table.index("_udeks_console_service_descriptor", capability)
        keyboard = table.index("_udeks_keyboard_service_descriptor", console)
        self.assertLess(capability, console)
        self.assertLess(console, keyboard)
        self.assertNotIn("_udeks_clock_service_descriptor", table)
        self.assertNotIn("_udeks_framebuffer_service_descriptor", table)
        self.assertIn("_udeks_time_service_descriptor", table)
        self.assertIn(".byte $09", table)

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

    def test_resident_time_service_uses_coherent_cia_tod_reads(self):
        source = (ROOT / "src/services/time/time.c").read_text(encoding="utf-8")
        descriptor = (ROOT / "src/services/time/descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertLess(source.index("CIA1_TOD_HOURS"), source.index("CIA1_TOD_TENTHS", source.index("sample_tod")))
        self.assertIn("UDEKS_VIDEO_PAL", source)
        self.assertIn("CIA1_CRA |= 0x80u", source)
        self.assertIn(".byte $04, $01", descriptor)
        self.assertIn(".addr _udeks_time_poll", descriptor)


if __name__ == "__main__":
    unittest.main()

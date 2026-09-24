# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PointerSourceTests(unittest.TestCase):
    def test_fixed_ports_are_sampled_without_leaking_cia_configuration(self):
        source = (ROOT / "src/8502/control_ports.s").read_text(encoding="utf-8")
        for declaration in (
            "CIA1_PRA                = $dc00",
            "CIA1_PRB                = $dc01",
            "CIA1_DDRA               = $dc02",
            "CIA1_DDRB               = $dc03",
            "SID_POTX                = $d419",
            "SID_POTY                = $d41a",
        ):
            self.assertIn(declaration, source)
        self.assertIn("and #$3f", source)
        self.assertIn("ora #$40", source)
        self.assertIn("lda #$c0", source)
        self.assertIn("sta saved_pra", source)
        self.assertIn("lda saved_pra", source)
        self.assertIn("lda saved_ddra", source)
        self.assertIn("lda saved_ddrb", source)
        self.assertIn("_udeks_control_ports_active", source)
        self.assertIn("active_switches", source)
        self.assertIn("sta saved_prb", source)
        self.assertIn("restore_after_activity", source)
        self.assertGreaterEqual(source.count("and active_switches"), 2)

    def test_mouse_driver_uses_modulo_64_noise_filtered_deltas(self):
        source = (ROOT / "src/services/input/mouse1351.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("& 0x7Fu", source)
        self.assertIn("delta < 0x40u", source)
        self.assertIn("delta >> 1", source)
        self.assertIn("0x80u - delta", source)
        self.assertIn("*dy = (signed char)-decode_axis", source)

    def test_joystick_driver_debounces_transitions(self):
        source = (ROOT / "src/services/input/joystick.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("candidate_state", source)
        self.assertIn("active != candidate_state", source)
        self.assertIn("udeks_joystick_initialize", source)

    def test_pointer_is_frame_paced_and_combines_both_sources(self):
        source = (ROOT / "src/services/input/pointer.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("VIC_RASTER < 200u", source)
        self.assertIn("udeks_mouse1351_decode", source)
        self.assertIn("udeks_joystick_decode", source)
        self.assertIn("mouse_dx + joystick_dx", source)
        self.assertIn("UDEKS_POINTER_X_MIN", source)
        self.assertIn("UDEKS_POINTER_X_MAX", source)

    def test_pointer_poll_precedes_keyboard_scan(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        pointer = table.index(".addr _udeks_pointer_service_descriptor")
        keyboard = table.index(".addr _udeks_keyboard_service_descriptor")
        self.assertLess(pointer, keyboard)
        descriptor = (
            ROOT / "src/services/input/pointer_descriptor.s"
        ).read_text(encoding="utf-8")
        self.assertIn(".byte $05, $01", descriptor)
        self.assertIn(".addr _udeks_pointer_poll", descriptor)

    def test_keyboard_isolated_during_control_port_activity(self):
        source = (ROOT / "src/services/input/keyboard.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("udeks_pointer_keyboard_allowed()", source)
        self.assertNotIn("VIC_RASTER", source)
        pointer = (ROOT / "src/services/input/pointer.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("VIC_RASTER - settle_raster", pointer)
        self.assertIn("< 26u", pointer)
        self.assertIn("warmup_samples = 2", pointer)
        self.assertIn("udeks_control_ports_active() != 0", pointer)


if __name__ == "__main__":
    unittest.main()

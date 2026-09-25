# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PointerSourceTests(unittest.TestCase):
    def test_fixed_ports_are_sampled_without_leaking_cia_configuration(self):
        source = (ROOT / "src/8502/pointer_irq.s").read_text(encoding="utf-8")
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
        self.assertIn("active_switches", source)
        self.assertIn("sta saved_prb", source)
        self.assertIn("and active_switches", source)

    def test_mouse_driver_uses_modulo_64_noise_filtered_deltas(self):
        source = (ROOT / "src/services/input/mouse1351.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("& 0x7Fu", source)
        self.assertIn("delta < 0x40u", source)
        self.assertIn("delta >> 1", source)
        self.assertIn("0x80u - delta", source)
        self.assertIn("*dy = (signed char)-decode_axis", source)
        self.assertIn('#pragma bss-name(push, "LOWBSS")', source)

    def test_joystick_driver_debounces_transitions(self):
        source = (ROOT / "src/services/input/joystick.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("candidate_state", source)
        self.assertIn("active != candidate_state", source)
        self.assertIn("udeks_joystick_initialize", source)

    def test_pointer_is_irq_paced_and_combines_both_sources(self):
        source = (ROOT / "src/8502/pointer_irq.s").read_text(encoding="utf-8")
        self.assertIn("RASTER_SELECT           = 200", source)
        self.assertIn("RASTER_SAMPLE           = 226", source)
        self.assertIn("decode_axis:", source)
        self.assertIn("sta total_dx", source)
        self.assertIn("sta total_dy", source)
        self.assertIn("apply_x_delta:", source)
        self.assertIn("apply_y_delta:", source)
        self.assertIn("_udeks_pointer_resynchronize:", source)
        self.assertIn("JOYSTICK_STEP           = 5", source)

        joystick = (ROOT / "include/udeks/joystick.h").read_text(
            encoding="utf-8"
        )
        self.assertIn("#define UDEKS_JOYSTICK_STEP     5", joystick)

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
        pointer = (ROOT / "src/8502/pointer_irq.s").read_text(encoding="utf-8")
        self.assertIn("lda PTR+26", pointer)
        self.assertIn("jsr _udeks_control_ports_active", pointer)
        self.assertIn("lda #$02\n        sta warmup_samples", pointer)
        scanner = (ROOT / "src/8502/keyboard_scan.s").read_text(
            encoding="utf-8"
        )
        routine = scanner.split("_udeks_keyboard_scan:", 1)[1]
        self.assertIn("php\n        sei", routine)
        self.assertIn("plp\n        rts", routine)

    def test_irq_crosses_bank_profiles_through_common_stubs(self):
        source = (ROOT / "src/8502/pointer_irq.s").read_text(encoding="utf-8")
        self.assertIn("IRQ_TRAMPOLINE          = $ffc5", source)
        self.assertIn("IRQ_RETURN              = $f909", source)
        self.assertIn("sta MMU_LCR_KERNEL_IO", source)
        self.assertIn("sta MMU_CR_ALWAYS", source)
        self.assertIn("irq_return_stub_end-irq_return_stub = 5", source)


if __name__ == "__main__":
    unittest.main()

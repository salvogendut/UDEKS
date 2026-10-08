# SPDX-License-Identifier: GPL-3.0-or-later
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from check_time_slot import validation_cases
from service_image import TIME_BASE, TIME_LIMIT, seal
from service_start_probe import retirement_trampoline


def image():
    data = bytearray(80)
    data[:8] = b'USVM\0\1\4\1'
    struct.pack_into('<7H', data, 8, TIME_BASE, 80, 10, 0, 0, 1, TIME_BASE+48)
    data[32:42] = b'USVC\0\1\4\1\0\x10'
    struct.pack_into('<3H', data, 42, TIME_BASE+51, TIME_BASE+54, TIME_BASE+57)
    data[48:] = b'\x60'*32
    return seal(data)


class TimeSlotQualificationTests(unittest.TestCase):
    def cases(self):
        return list(struct.iter_unpack('<BBHHB', validation_cases(image())))

    def test_independent_oracle_is_deterministic_and_covers_both_outcomes(self):
        original = bytearray(image())
        before = bytes(original)
        result = validation_cases(original)
        self.assertEqual(original, before)
        self.assertEqual(result, validation_cases(before))
        self.assertEqual(len(result)//7, 436)
        self.assertEqual({c[-1] for c in self.cases()}, {0, 1})

    def test_checksum_negatives_are_not_accidentally_resealed(self):
        negatives = [c for c in self.cases() if c[1] == 3]
        self.assertEqual([(c[0], c[-1]) for c in negatives], [(16, 1), (17, 1)])

    def test_received_length_is_separate_from_header_claim(self):
        cases = {c[3]: c[-1] for c in self.cases() if c[1] == 0}
        self.assertEqual(cases[80], 0)
        for count in (0, 1, 47, 48, 79, 81, 0xffff):
            self.assertEqual(cases[count], 1)

    def test_bss_exact_fit_and_wrapping_addition_are_present(self):
        cases = {c[2]: c[-1] for c in self.cases() if c[:2] == (12, 2)}
        spare = TIME_LIMIT-TIME_BASE-80
        self.assertEqual(cases[spare], 0)
        for size in (spare+1, 0xffff-80, 0x10000-80, 0xffff):
            self.assertEqual(cases[size], 1)

    def test_all_four_vectors_have_lower_and_upper_boundary_cases(self):
        for offset in (20, 42, 44, 46):
            cases = {c[2]: c[-1] for c in self.cases() if c[:2] == (offset, 2)}
            for value in (TIME_BASE, TIME_BASE+47, TIME_BASE+80, TIME_LIMIT, 0xffff):
                self.assertEqual(cases[value], 1)
            self.assertEqual(cases[TIME_BASE+48], 0)
            self.assertEqual(cases[TIME_BASE+79], 0)

    def test_retirement_probe_corrupts_then_calls_without_resuming_os(self):
        code = retirement_trampoline(0x2345, 0x3456)
        # SEI/CLD, clear exactly 24 diagnostic bytes, poison retired entry,
        # JSR guard, store result + completion, stop. No stale poll can write
        # the record between corruption and the repeated startup call.
        self.assertEqual(code[:12], bytes.fromhex('78 d8 a9 00 a2 17 9d 90 f0 ca 10 fa'))
        self.assertEqual(code[12:20], bytes.fromhex('a9 02 8d 56 34 20 45 23'))
        self.assertEqual(code[20:31], bytes.fromhex('8d 20 0b a9 a5 8d 21 0b 4c 1c 0b'))
        self.assertEqual(code[0x20:], b'\xff\0')
        self.assertEqual(len(code), 34)  # bounded VICE monitor byte list

    def test_simulator_corrupts_the_actual_published_registry_address(self):
        header = (ROOT/'include/udeks/service.h').read_text()
        fixture = (ROOT/'bench/time-module/slot_check.c').read_text()
        self.assertIn('0xF090u', header)
        self.assertIn('memset((void *)0xf090,0,24)', fixture)

    def test_manager_is_not_linked_into_boot_or_advertised_as_syscall(self):
        make = (ROOT/'Makefile').read_text()
        self.assertNotIn('time-slot.o', make)
        self.assertNotIn('time_slot.s', make)
        source = (ROOT/'src/services/module/time_slot.s').read_text()
        self.assertIn('not linked into normal boot yet', source)
        self.assertIn('received byte count', source)


if __name__ == '__main__':
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import hashlib
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from graphics_code_budget import compare_sizes, resident_gap, split_trace


class GraphicsCodeBudget(unittest.TestCase):
    def setUp(self):
        self.reference = dict(CODE=8055, RODATA=130, BSS=4, HIGHBSS=88, DATA=0)
        self.candidate = dict(self.reference, CODE=7142)

    def test_state_preserving_measured_object_is_required_in_link(self):
        self.assertEqual(compare_sizes(self.reference, self.candidate, self.candidate), 913)
        with self.assertRaisesRegex(ValueError, 'production link'):
            compare_sizes(self.reference, self.candidate, self.reference)

    def test_new_or_growing_state_fails_even_when_code_is_smaller(self):
        for key in ('BSS', 'HIGHBSS', 'ZEROPAGE', 'DATA', 'OTHER'):
            candidate = dict(self.candidate)
            candidate[key] = candidate.get(key, 0)+1
            with self.assertRaisesRegex(ValueError, 'state/data'):
                compare_sizes(self.reference, candidate, candidate)

    def test_no_saving_is_not_a_success(self):
        with self.assertRaisesRegex(ValueError, 'did not reclaim'):
            compare_sizes(self.reference, self.reference, self.reference)

    def test_gap_uses_inclusive_end_and_does_not_count_boot_overlay(self):
        segments = {'BSS': (0x8cb0, 0x9083, 980), 'SERVICEBOOT': (0x93d0, 0x95d5, 518)}
        self.assertEqual(resident_gap(segments), 844)
        segments['BSS'] = (0x8cb0, 0x93d0, 0)
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            resident_gap(segments)
        with self.assertRaises(KeyError):
            resident_gap({'BSS': (0, 0, 0)})

    def test_simulator_footer_is_not_part_of_binary_trace(self):
        self.assertEqual(split_trace(b'\x01\x002 cycles\n'), (b'\x01\x00', 2))
        for invalid in (b'', b'2 cycles\n', b'\0\0', b'\0x cycles\n', b'\0' + b'23 cycles\n'):
            with self.assertRaises(ValueError):
                split_trace(invalid)

    def test_preserved_reclaim_and_emulator_evidence_is_bound(self):
        evidence = Path(__file__).resolve().parents[1]/'bench/results/2026-10-09-graphics-code-budget'
        for line in (evidence/'SHA256SUMS').read_text().splitlines():
            expected, name = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((evidence/name).read_bytes()).hexdigest(), expected, name)
        report = json.loads((evidence/'budget.json').read_text())
        trace = (evidence/'sim6502/baseline.trace').read_bytes()
        self.assertEqual(trace, (evidence/'sim6502/compact.trace').read_bytes())
        self.assertEqual(len(trace), report['trace_bytes'])
        self.assertEqual(hashlib.sha256(trace).hexdigest(), report['trace_sha256'])
        self.assertEqual(report['object_code_saved'], 913)
        self.assertEqual(report['resident_free_bytes'], 844)
        vice = json.loads((evidence/'vice/d71.json').read_text())
        native = json.loads((evidence/'1986/d81.json').read_text())
        self.assertEqual(vice['disk_sha256'], report['disk_sha256']['d71'])
        self.assertEqual(native['disk_sha256'], report['disk_sha256']['d81'])
        self.assertEqual(native['exit_status'], 0)
        self.assertTrue(native['four_native'])
        self.assertIn('PASS four native:', (evidence/'1986/d81.log').read_text())


if __name__ == '__main__':
    unittest.main()

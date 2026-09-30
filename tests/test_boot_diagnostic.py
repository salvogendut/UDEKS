# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from boot_diagnostic import diagnostic_image


class BootDiagnosticTests(unittest.TestCase):
    def test_exactly_one_operand_changes_and_original_stays_intact(self):
        original = (ROOT/'bench/artifacts/2026-09-30-disk-commands/udeks.d64').read_bytes()
        result = diagnostic_image(original)
        changes = [i for i, (a, b) in enumerate(zip(original, result)) if a != b]
        self.assertEqual(len(result), len(original))
        self.assertEqual(len(changes), 1)
        offset = changes[0]
        self.assertEqual(original[offset-1:offset+4], b'\xa9\x00\x20\x90\xff')
        self.assertEqual(result[offset-1:offset+4], b'\xa9\xff\x20\x90\xff')
        with self.assertRaises(ValueError):
            diagnostic_image(result)

    def test_rejects_unknown_boot_loader(self):
        with self.assertRaises(ValueError):
            diagnostic_image(bytes(174848))


if __name__ == '__main__': unittest.main()

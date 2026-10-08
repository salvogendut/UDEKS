# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from storage_mutate_probe import SAMPLES, fixture, read_files


class MutationMedia(unittest.TestCase):
    def test_disposable_fixtures_preserve_exact_types_and_binary_bytes(self):
        for drive in ('1541', '1571', '1581'):
            with self.subTest(drive=drive):
                self.assertEqual(read_files(fixture(drive), drive), SAMPLES)
        self.assertEqual(SAMPLES['EMPTY'], (0x81, b''))
        self.assertEqual(SAMPLES['SRCPRG'][1][:2], b'\0\x0e')
        self.assertEqual(len('LONGSOURCE123456'), 16)

    def test_fixtures_are_deterministic(self):
        for drive in ('1541', '1571', '1581'):
            self.assertEqual(fixture(drive), fixture(drive))


# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'bench/artifacts/2026-09-29-repaint-policy'
RESULT = ROOT / 'bench/results/2026-09-29-repaint-policy'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WindowRepaintBudgetEvidenceTests(unittest.TestCase):
    def test_target_measurement_is_compile_only_and_binds_all_actual_inputs_outputs(self):
        report = json.loads((RESULT / 'budget.json').read_text())
        self.assertIn('lower bound, not linked runtime closure', report['scope'])
        for name, sha in report['input_sha256'].items():
            self.assertEqual(digest(ART / 'inputs' / name), sha, name)
        for name, sha in report['output_sha256'].items():
            self.assertEqual(digest(ART / 'build' / name), sha, name)
        self.assertEqual(report['sizes']['CODE'], 4643)
        self.assertTrue(all(report['sizes'][name] == 0 for name in ('BSS', 'DATA', 'ZEROPAGE')))
        self.assertEqual(report['cc65_layout'], {'job': 22, 'ticket': 9, 'work': 15, 'window': 9})
        self.assertEqual((ART / 'build/layout.bin').read_bytes(), bytes([22, 9, 15, 9]))
        names = [name for name, _ in report['imports']]
        self.assertEqual(names, sorted(set(names)))

    def test_manifests_cover_all_preserved_files(self):
        for directory in (ART, RESULT):
            declared = {}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                declared[name] = sha
                self.assertEqual(digest(directory / name), sha, name)
            self.assertEqual(set(declared), {str(path.relative_to(directory)) for path in directory.rglob('*')
                if path.is_file() and path.name != 'SHA256SUMS'})

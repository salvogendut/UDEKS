# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'bench/artifacts/2026-09-29-repaint-compact'
RESULT = ROOT / 'bench/results/2026-09-29-repaint-compact'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WindowRepaintCompactEvidenceTests(unittest.TestCase):
    def test_state_reclaim_is_closed_link_budget_only_and_binds_inputs_outputs(self):
        report = json.loads((RESULT / 'budget.json').read_text())
        self.assertIn('UNBOOTABLE', report['scope'])
        inputs = dict(report['input_sha256'])
        for entry in report['links'].values():
            inputs.update(entry['input_sha256'])
        for name, sha in inputs.items():
            self.assertEqual(digest(ART / 'inputs' / name), sha, name)
        for name, sha in report['output_sha256'].items():
            self.assertEqual(digest(ART / 'build' / name), sha, name)
        baseline, compact = (report['variants'][key] for key in ('baseline', 'compact'))
        self.assertEqual(baseline['segments']['CODE'], 7762)
        self.assertEqual(compact['segments']['CODE'], 7645)
        self.assertEqual(baseline['segments']['HIGHBSS'], 88)
        self.assertEqual(compact['segments']['HIGHBSS'], 76)
        self.assertEqual(baseline['imports'], compact['imports'])
        self.assertEqual(report['state']['reclaimed'], 12)
        self.assertEqual(report['state']['remaining_job_shortfall'], 10)
        for variant in ('normal', 'panic'):
            entry = report['links'][variant]
            self.assertEqual(entry['code_saved'], 117)
            self.assertEqual(entry['highbss_saved'], 12)
            self.assertEqual(entry['baseline']['VICSHADOW']['start'], 0xA1E0)
            self.assertEqual(entry['compact']['VICSHADOW']['start'], 0xA16B)
            self.assertEqual(entry['baseline']['HIGHBSS']['end'], 0xE2E1)
            self.assertEqual(entry['compact']['HIGHBSS']['end'], 0xE2D5)
            self.assertTrue(entry['library_modules'])
            self.assertEqual(entry['baseline']['SYSCALLS'], entry['compact']['SYSCALLS'])
            self.assertEqual(entry['baseline']['TASKGATE'], entry['compact']['TASKGATE'])
        self.assertEqual(set(report['toolchain']), {'cc65', 'ca65', 'ld65', 'cl65'})
        self.assertEqual(digest(ART / 'build' / report['library_provider']['archived']),
                         report['library_provider']['sha256'])

    def test_manifests_cover_all_preserved_files(self):
        for directory in (ART, RESULT):
            declared = {}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                declared[name] = sha
                self.assertEqual(digest(directory / name), sha, name)
            self.assertEqual(set(declared), {str(path.relative_to(directory)) for path in directory.rglob('*')
                if path.is_file() and path.name != 'SHA256SUMS'})

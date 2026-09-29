# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'bench/artifacts/2026-09-29-window-cache-integration'
RESULT = ROOT / 'bench/results/2026-09-29-window-cache-integration'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WindowCacheIntegrationEvidenceTests(unittest.TestCase):
    def test_complete_input_and_result_bindings_and_no_rom_snapshots(self):
        report = json.loads((RESULT / 'report.json').read_text())
        for name, sha in report['inputs_sha256'].items():
            self.assertEqual(digest(ART / 'inputs' / name), sha, name)
        self.assertFalse(any(p.suffix.lower() in ('.vsf', '.rom') for p in ART.rglob('*')))
        self.assertNotIn('tools/window_cache_live.py', report['inputs_sha256'])
        for engine in ('1986', 'vice'):
            run = json.loads((RESULT / f'{engine}-run.json').read_text())
            self.assertEqual(run['report_sha256'], digest(RESULT / 'report.json'))
            self.assertEqual(set(run['results']), {'d64', 'd71'})
            for name, sha in run['raw_sha256'].items():
                self.assertEqual(digest(RESULT / name), sha, name)
        native = json.loads((RESULT / '1986-run.json').read_text())
        self.assertEqual(digest(ART / 'native'), native['runner_sha256'])
        self.assertEqual(digest(RESULT / 'native.c'), native['source_sha256'])
        for fmt, sha in report['disk_sha256'].items():
            self.assertEqual(digest(RESULT / f'udeks-cache.{fmt}'), sha)
            self.assertEqual(digest(RESULT / f'1986-{fmt}.log'), native['results'][fmt]['log_sha256'])
            self.assertIn('PASS: live cached moves, full pixels, fallback, cancellation and restart',
                          (RESULT / f'1986-{fmt}.log').read_text())

    def test_source_only_clean_build_and_configuration_switch_reproduce_images(self):
        clean = json.loads((RESULT / 'clean-build.json').read_text())
        report = json.loads((RESULT / 'report.json').read_text())
        self.assertEqual(clean['selected'], report['disk_sha256'])
        self.assertEqual(clean['selected_again'], report['disk_sha256'])
        self.assertEqual(clean['default'], {
            'd64': '65a37c265a0a9d4e355fdf4738b764ffa42c64565d4fea305ff152ac323b0483',
            'd71': 'd99463d6f84c0b54cd9178056013368f85e9fea16b2800ed75470909b5a2a2d6'})
        for name, sha in clean['log_sha256'].items():
            self.assertEqual(digest(RESULT / name), sha)
            self.assertIn('placement audit OK', (RESULT / name).read_text())
        module = ART / 'inputs/build/window-cache/module.bin'
        self.assertEqual(digest(module), '758965e4f32ae6f267c662b6da340caac4c9db03785ef4c4f18f002dc20b5bd0')
        self.assertEqual(digest(ART / 'inputs/build/8502/udeks-8502.bin'),
                         'dfef7e6dfea3759f57d2fc35eaa62eab6d1f58e7f950f1dea1020c7ca8152a80')

    def test_actual_selected_disk_clock_start_guard_and_settled_input_shutdown(self):
        run = json.loads((RESULT / 'latency/run.json').read_text())
        native = json.loads((RESULT / '1986-run.json').read_text())
        self.assertEqual(run['provenance'], native['provenance'])
        self.assertEqual(digest(ART / 'latency/native'), run['runner_sha256'])
        self.assertEqual(digest(ART / 'latency/native.c'), run['source_sha256'])
        for name, sha in run['input_sha256'].items():
            if name.startswith('build/window-cache-integration/'):
                path = RESULT / Path(name).name
            else:
                path = ART / 'inputs' / name
            self.assertEqual(digest(path), sha, name)
        for fmt, sha in run['log_sha256'].items():
            path = RESULT / 'latency' / (fmt + '.log')
            self.assertEqual(digest(path), sha)
            found = dict(re.findall(r'^(clock drag start|overlap clock drag start): frames=(\d+)$',
                                    path.read_text(), re.M))
            self.assertEqual(set(found), {'clock drag start', 'overlap clock drag start'})
            self.assertTrue(all(0 < int(value) <= 30 for value in found.values()))
            self.assertIn('PASS: native clock-only/overlap drag-start timing and shutdown', path.read_text())

    def test_immutable_manifests_cover_every_evidence_file(self):
        for directory in (ART, RESULT):
            declared = {}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                declared[name] = sha
                self.assertEqual(digest(directory / name), sha, name)
            actual = {str(p.relative_to(directory)) for p in directory.rglob('*')
                      if p.is_file() and p.name != 'SHA256SUMS'}
            self.assertEqual(set(declared), actual)


if __name__ == '__main__':
    unittest.main()

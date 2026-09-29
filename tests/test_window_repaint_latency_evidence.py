# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_repaint_latency import measurements

ART = ROOT / 'bench/artifacts/2026-09-29-window-repaint-baseline'
RESULT = ROOT / 'bench/results/2026-09-29-window-repaint-baseline'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WindowRepaintLatencyEvidenceTests(unittest.TestCase):
    def test_inputs_runner_and_both_format_results_are_source_bound(self):
        run = json.loads((RESULT / 'run.json').read_text())
        retained = json.loads((RESULT / 'preserved-inputs.json').read_text())
        self.assertEqual(set(retained), set(run['input_sha256']))
        for name, sha in run['input_sha256'].items():
            self.assertEqual(digest(ART / retained[name]), sha, name)
        self.assertEqual(digest(ART / 'native'), run['runner_sha256'])
        self.assertEqual(digest(RESULT / 'native.c'), run['source_sha256'])
        self.assertEqual(set(run['results']), {'d71', 'd64'})
        for fmt in ('d71', 'd64'):
            log = RESULT / (fmt + '.log')
            self.assertEqual(digest(log), run['log_sha256'][fmt])
            self.assertEqual(measurements(log.read_text()), run['results'][fmt])
        self.assertEqual(run['results']['d71'], run['results']['d64'])
        self.assertEqual(run['time_unit'], 'emulated bus cycles, includes interrupts and CPU handoffs')

    def test_manifests_cover_all_preserved_files_and_exclude_rom_snapshots(self):
        for directory in (ART, RESULT):
            declared = {}
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                declared[name] = sha
                self.assertEqual(digest(directory / name), sha, name)
                self.assertNotIn(Path(name).suffix.lower(), ('.vsf', '.rom'))
            self.assertEqual(set(declared), {str(path.relative_to(directory)) for path in directory.rglob('*')
                if path.is_file() and path.name != 'SHA256SUMS'})


if __name__ == '__main__':
    unittest.main()

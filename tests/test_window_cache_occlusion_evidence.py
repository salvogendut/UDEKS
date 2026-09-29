# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_cache_occlusion import clock_measurements
from window_cache_repaint import measurements

NAME = '2026-09-28-window-cache-occlusion'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WindowCacheOcclusionEvidenceTests(unittest.TestCase):
    def test_both_variants_have_complete_hash_bound_rom_free_archives(self):
        for name in (NAME, NAME+'-reference'):
            for kind in ('artifacts', 'results'):
                directory = ROOT / 'bench' / kind / name
                self.assertFalse(list(directory.rglob('*.vsf')))
                manifest = (directory / 'SHA256SUMS').read_text().splitlines()
                names = set()
                for line in manifest:
                    digest, relative = line.split('  ', 1)
                    self.assertNotIn(relative, names)
                    names.add(relative)
                    self.assertEqual(sha(directory / relative), digest, relative)
                self.assertEqual(names, {str(p.relative_to(directory)) for p in directory.rglob('*')
                    if p.is_file() and p != directory / 'SHA256SUMS'})

    def test_comparison_is_bound_to_exact_runs_logs_and_complete_case_canvases(self):
        comparison = json.loads((ROOT / 'bench/results' / NAME / 'comparison.json').read_text())
        self.assertEqual(comparison, json.loads((ROOT / 'bench/results' / (NAME+'-reference') / 'comparison.json').read_text()))
        for path, digest in comparison['inputs_sha256'].items():
            work, filename = Path(path).parts[1:]
            name = NAME+('-reference' if work.endswith('-reference') else '')
            directory = ROOT / 'bench'
            archived = directory / 'artifacts' / name / 'build' / filename if filename == 'report.json' else directory / 'results' / name / filename
            self.assertEqual(sha(archived), digest, path)
        for fmt in ('d71', 'd64'):
            pair = comparison['values'][fmt]
            for variant, name in (('reference', NAME+'-reference'), ('occlusion', NAME)):
                result = ROOT / 'bench/results' / name
                log = (result / f'1986-{fmt}.log').read_text()
                expected = measurements(log)
                expected['clock_repairs'] = clock_measurements(log)
                self.assertEqual(pair[variant], expected)
                self.assertIn('PASS: live cached moves, full pixels, fallback, cancellation and restart', log)
                binding = json.loads((result / '1986-run.json').read_text())
                for case in range(3):
                    for surface in ('shadow', 'bitmap'):
                        path = result / f'1986-{fmt}-clock-{case}-{surface}.bin'
                        self.assertEqual(sha(path), binding['raw_sha256'][path.name])
                        self.assertEqual(len(path.read_bytes()), 8000)
                        reference = ROOT / 'bench/results' / (NAME+'-reference') / f'1986-{fmt}-clock-{case}-shadow.bin'
                        self.assertEqual(path.read_bytes(), reference.read_bytes())
            for case in (0, 1):
                before, after = pair['reference']['clock_repairs'][case], pair['occlusion']['clock_repairs'][case]
                self.assertLess(after['frames'], before['frames'])
                self.assertLess(after['pages'], before['pages'])
            self.assertEqual([v['pages'] for v in pair['occlusion']['clock_repairs']], [0, 2, 33])
            # This is a clock repair improvement, not a broad median-move claim.
            self.assertEqual(pair['occlusion']['median_paste_page_copies'], 22.5)
            self.assertEqual(pair['occlusion']['worst_paste_frames'], 163)

    def test_link_geometry_runtime_helpers_and_both_emulator_bindings(self):
        reports = []
        for name in (NAME+'-reference', NAME):
            artifact = ROOT / 'bench/artifacts' / name
            result = ROOT / 'bench/results' / name
            path = artifact / 'build/report.json'
            report = json.loads(path.read_text())
            reports.append(report)
            self.assertEqual(report['manager_sizes']['HIGHBSS'], 88)
            self.assertEqual(report['transport_bytes'], 377)
            self.assertEqual(report['segments']['VICSHADOW'], {'start': 0xa1e0, 'end': 0xc11f, 'size': 8000})
            for fmt, digest in report['disk_sha256'].items():
                self.assertEqual(sha(artifact / 'build' / ('udeks-cache.'+fmt)), digest)
            for engine in ('1986', 'vice'):
                binding = json.loads((result / (engine+'-run.json')).read_text())
                self.assertEqual(binding['report_sha256'], sha(path))
                self.assertEqual(set(binding['results']), {'d71', 'd64'})
                for filename, digest in binding['raw_sha256'].items():
                    self.assertEqual(sha(result / filename), digest)
                for item in binding['results'].values():
                    self.assertEqual(item['pixels'], 17472)
            native = json.loads((result / '1986-run.json').read_text())
            self.assertEqual(native['runner_sha256'], sha(artifact / 'build/native'))
            self.assertEqual(native['source_sha256'], sha(artifact / 'build/native.c'))
        self.assertEqual(reports[0]['segments'], reports[1]['segments'])
        self.assertEqual(reports[0]['helpers'], reports[1]['helpers'])
        self.assertEqual(reports[0]['normal_disks'], reports[1]['normal_disks'])
        self.assertEqual(reports[1]['manager_sizes']['CODE'], 7695)
        self.assertEqual(reports[1]['remaining_padding'], 87)


if __name__ == '__main__':
    unittest.main()

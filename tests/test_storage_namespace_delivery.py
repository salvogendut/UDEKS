# SPDX-License-Identifier: GPL-3.0-or-later
"""Compact namespace machine evidence and private-backend placement gate."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from storage_mutation_layout import headroom
from build_scheduler_overlay import map_segments

A = ROOT / 'bench/artifacts/2026-10-08-storage-namespace'
R = ROOT / 'bench/results/2026-10-08-storage-namespace'
OLD = ROOT / 'bench/artifacts/2026-10-08-storage-files/storage.map'


def report(name):
    return json.loads((R / (name + '.json')).read_text())


def fixture(**overrides):
    segments = map_segments((A / 'storage.map').read_text())
    segments.update(overrides)
    return '\n'.join(f'{name} {start:06X} {end:06X} {size:06X} 00001'
                     for name, (start, end, size) in segments.items())


class StorageNamespaceLayout(unittest.TestCase):
    def test_qualified_maps_and_actual_reclaim(self):
        before = headroom(OLD.read_text())
        current = headroom((A / 'storage.map').read_text())
        candidate = headroom((A / 'with-backend.map').read_text())
        self.assertEqual(current, report('layout')['production'])
        self.assertEqual(candidate, report('layout')['with_backend'])
        self.assertEqual(current['code_total'] - before['code_total'], 1675)
        self.assertEqual(current['BSS'] - before['BSS'], 54)
        self.assertEqual(candidate['code_total'], 563)
        self.assertEqual(candidate['BSS'], 19)

    def test_overflow_rejected_in_every_region(self):
        for name, end in (('CODE', 0x1880), ('STORAGECODE', 0xc600),
                          ('BSS', 0xe180), ('IECCODE', 0xe900), ('STORAGEHIGH', 0xff00)):
            with self.subTest(segment=name):
                start = map_segments(fixture())[name][0]
                with self.assertRaises(ValueError):
                    headroom(fixture(**{name: (start, end, end + 1 - start)}))

    def test_missing_segments_fail_instead_of_false_headroom(self):
        for name in ('CODE', 'BSS', 'RODATA', 'IECCODE', 'STORAGEHIGH'):
            with self.subTest(segment=name):
                text = '\n'.join(line for line in fixture().splitlines()
                                 if not line.startswith(name + ' '))
                with self.assertRaises(ValueError):
                    headroom(text)

    def test_moved_state_does_not_borrow_stack_or_app_space(self):
        with self.assertRaises(ValueError):
            headroom(fixture(BSS=(0xdf00, 0xe049, 330)))

    def test_inconsistent_sizes_and_unexpected_segments_fail(self):
        with self.assertRaises(ValueError):
            headroom(fixture(BSS=(0xe000, 0xe149, 329)))
        with self.assertRaises(ValueError):
            headroom(fixture(EXTRA=(0xc600, 0xc6ff, 256)))

    def test_data_after_code_counts_toward_occupied_space(self):
        original = headroom(fixture())
        self.assertEqual(headroom(fixture(DATA=(0x1813, 0x181f, 13)))['CODE'],
                         original['CODE'] - 13)
        with self.assertRaises(ValueError):
            headroom(fixture(DATA=(0x1813, 0x1880, 110)))


class StorageNamespaceEvidence(unittest.TestCase):
    def test_all_artifacts_and_results_are_hash_checked(self):
        for folder in (A, R):
            named = set()
            for line in (folder / 'SHA256SUMS').read_text().splitlines():
                expected, name = line.split()
                self.assertNotIn(name, named)
                named.add(name)
                self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), expected)
            self.assertEqual(named, {p.name for p in folder.iterdir() if p.name != 'SHA256SUMS'})

    def test_machine_oracle_and_negative_control(self):
        q = report('qualification')
        self.assertEqual(q['positive_exit_status'], 0)
        self.assertEqual(q['negative_exit_status'], 1)
        self.assertEqual(q['cases'], 36532)
        self.assertIn('PASS 36532 namespace cases', (R / 'namespace.log').read_text())
        self.assertIn('FAIL resolve case 1: got 0 expected 22', (R / 'negative.log').read_text())
        self.assertNotEqual((A / 'namespace.sim65').read_bytes(), (A / 'negative.sim65').read_bytes())
        self.assertFalse(q['production_has_mutation_backend'])
        self.assertFalse(q['hardware_acceptance'])
        self.assertIn('cbm_mutate.o:', (A / 'with-backend.map').read_text())
        self.assertNotIn('cbm_mutate.o:', (A / 'storage.map').read_text())

    def test_live_reports_refer_to_same_candidate_and_preserve_files(self):
        q = report('qualification')
        disk_hash = hashlib.sha256((A / 'udeks.d64').read_bytes()).hexdigest()
        self.assertEqual(disk_hash, q['images']['1541'])
        self.assertEqual(report('native-1986')['disk_sha256'], disk_hash)
        self.assertEqual(report('native-1986')['existing_files_unchanged'], 23)
        self.assertEqual(report('native-1986')['phases'], ['create', 'reboot'])
        for drive in ('1541', '1571', '1581'):
            result = report('public-' + drive)
            self.assertEqual(result['disk_sha256'], q['images'][drive])
            self.assertEqual(result['original_files_unchanged'], 23)
            self.assertEqual(result['created']['BOOTRW'], 24)
            self.assertEqual(result['created']['EMPTY'], 0)
            self.assertTrue(any(row['status'] == 1 and 'Read-only filesystem' in row['console']
                                for row in result['checks']))
            self.assertTrue(any(row['boot'] == 1 and row['command'] == 'save -c /WRTEST 515'
                                and row['status'] == 0 for row in result['checks']))

    def test_recovery_still_loads_an_independent_disk_program(self):
        recovery = report('recovery')
        self.assertTrue(recovery['recovery'])
        self.assertTrue(recovery['driver_intact'])
        self.assertIn('/mnt/RECOVER recovery', [row['command'] for row in recovery['commands']])
        self.assertIn('namespace-ok', recovery['commands'][-1]['console'])

# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import window_cache_compact_delivery as compact
import window_cache_controller_delivery as delivery

ARTIFACT = ROOT / 'bench/artifacts' / compact.NAME
RESULT = ROOT / 'bench/results' / compact.NAME


class WindowCacheCompactDeliveryTests(unittest.TestCase):
    def test_whole_compact_module_including_gateway_and_slack_is_checked(self):
        module = compact.qualified_module()
        slot = delivery.fixture(module)
        self.assertEqual(len(module), 4106)
        self.assertEqual(slot[0xf46:0x100a], compact.GATEWAY.read_bytes())
        self.assertEqual(slot[0x100a:0x1010], bytes(6))
        self.assertEqual(int.from_bytes(slot[0x101a:0x101c], 'little'), sum(module)&65535)
        delivery.validate_slot(slot, module)
        for offset in (0, 212, 213, 0xf46, 0x1009, 0x100a, 0x1010, 0x101f):
            bad = bytearray(slot); bad[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                delivery.validate_slot(bad, module)

    def test_archive_binds_inputs_links_disks_and_exact_scheduler(self):
        build = ARTIFACT / 'build'
        report = json.loads((build / 'build-report.json').read_text())
        module = (build / 'core.bin').read_bytes()
        self.assertEqual(module, compact.qualified_module())
        scheduler = (ARTIFACT / 'build/boot/scheduler-overlay.prg').read_bytes()
        payload = (build / 'secondary.prg').read_bytes()
        self.assertEqual(payload, delivery.envelope(scheduler, module))
        self.assertEqual(payload[2+0x1e00:], scheduler[2:])
        self.assertEqual(report['secondary_end'], 0x7229)
        self.assertEqual(report['resident_delivery_bytes_added'], 0)
        self.assertEqual((report['resident_transport_bytes'], report['remaining_before_hooks']), (371, 131))
        self.assertEqual((report['gateway_source'], report['gateway_bytes']), (0x5146, 196))
        for key, root in (('inputs_sha256', ARTIFACT), ('linked_sha256', build), ('disk_sha256', build)):
            for name, sha in report[key].items():
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), sha, name)
        for name, deltas in report['relocation_deltas'].items():
            old = (ARTIFACT / 'build/boot' / (name+'.bin')).read_bytes()
            new = (build / (name+'.bin')).read_bytes()
            self.assertEqual(len(old), len(new))
            self.assertEqual([(i,a,b) for i,(a,b) in enumerate(zip(old,new)) if a!=b], [tuple(v) for v in deltas])

    def test_two_formats_two_emulators_bind_complete_lifetime_and_input_gates(self):
        report_path = ARTIFACT / 'build/build-report.json'
        report = json.loads(report_path.read_text())
        module = (ARTIFACT / 'build/core.bin').read_bytes()
        for engine in ('vice', '1986'):
            binding = json.loads((RESULT / f'{engine}-binding.json').read_text())
            self.assertEqual(binding['build_report_sha256'], hashlib.sha256(report_path.read_bytes()).hexdigest())
            self.assertEqual(binding['disk_sha256'], report['disk_sha256'])
            self.assertEqual(len(binding['raw_sha256']), 18 if engine=='vice' else 6)
            for name, sha in binding['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((RESULT / name).read_bytes()).hexdigest(), sha, name)
            results = json.loads((RESULT / f'{engine}-results.json').read_text())
            self.assertEqual(set(results), {'d71', 'd64'})
            for fmt in results:
                if engine == 'vice':
                    self.assertEqual(set(results[fmt]), delivery.LABELS)
                    for label in delivery.LABELS:
                        raw = (RESULT / f'vice-{fmt}-{label}-core.bin').read_bytes()
                        self.assertEqual(raw[:2], b'\x00\x42')
                        self.assertEqual(delivery.validate_slot(raw[2:], module), results[fmt][label])
                else:
                    raw = (RESULT / f'1986-{fmt}-core.bin').read_bytes()
                    self.assertEqual(delivery.validate_slot(raw, module), results[fmt])
                    log = (RESULT / f'1986-{fmt}.log').read_text()
                    self.assertEqual(sum(s.startswith('stress ') for s in log.splitlines()), 32)
                    self.assertIn('PASS: repeated native wave drags and console cancellation', log)

    def test_preserved_manifests(self):
        for directory in (ARTIFACT, RESULT):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), sha, name)

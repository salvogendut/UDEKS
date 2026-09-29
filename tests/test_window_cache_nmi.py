# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_cache_nmi import NAME, decode, negative
from window_cache_command import reference


def synthetic(case=0):
    data = bytearray(8096)
    data[:8] = b'NMIC\x01\x02' + bytes((case, 0))
    rows, calls, images = (132, 543, 66) if case == 0 else (312, 336, 2)
    data[8:10] = rows.to_bytes(2, 'little')
    data[10:12] = calls.to_bytes(2, 'little')
    data[12] = 1
    data[14] = images
    data[22] = 217
    data[23] = 15
    data[26:30] = (1000).to_bytes(4, 'little')
    data[30:34] = (100).to_bytes(4, 'little')
    data[34:36] = (1000).to_bytes(2, 'little')
    data[64:] = reference(case)
    return data


class WindowCacheNmiTests(unittest.TestCase):
    def test_decoder_requires_worker_and_kernel_arrivals_exact_drains_and_pixels(self):
        for case in (0, 1):
            good = synthetic(case)
            self.assertEqual(decode(good, case)['nmi_drains'], 1000)
            for offset in (0, 5, 8, 15, 26, 34, 36, 37, 38, 63, 64, 8095):
                bad = bytearray(good)
                bad[offset] ^= 1
                with self.subTest(case=case, offset=offset), self.assertRaises(ValueError):
                    decode(bad, case)
            for value in (0, 1000, 1001):
                bad = bytearray(good)
                bad[30:34] = value.to_bytes(4, 'little')
                with self.assertRaises(ValueError):
                    decode(bad, case)
            bad = bytearray(good)
            bad[26:30] = (65536).to_bytes(4, 'little')
            with self.assertRaises(ValueError):
                decode(bad, case)

    def test_no_pending_fault_keeps_pixels_correct_but_cannot_pass(self):
        data = synthetic()
        data[26:30] = (1).to_bytes(4, 'little')
        data[30:36] = bytes(6)
        self.assertEqual(negative(data)['nmi_total'], 1)
        with self.assertRaises(ValueError):
            decode(data, 0)
        for offset in (26, 34, 36, 37, 8095):
            bad = bytearray(data)
            bad[offset] ^= 1
            with self.assertRaises(ValueError):
                negative(bad)

    def test_exact_stub_private_state_and_one_byte_live_negative(self):
        directory = ROOT / 'bench/artifacts' / NAME
        build = directory / 'build'
        report = json.loads((build / 'build-report.json').read_text())
        self.assertEqual(report['nmi_object']['CODE'], 71)
        self.assertTrue(all(size == 0 for name, size in report['nmi_object'].items() if name != 'CODE'))
        stub = bytes.fromhex(report['stub_hex'])
        self.assertEqual(stub, b'\x48\xa9\x01\x8d\xf5\xff\x68\x40')
        good = (build / 'probe-0.prg').read_bytes()
        bad = (build / 'probe-no-pending.prg').read_bytes()
        self.assertEqual(good.count(stub), 1)
        position = good.index(stub) + 3
        self.assertEqual(report['negative_control'], {'offset': position, 'before': 0x8d, 'after': 0x2c})
        self.assertEqual(len(good), len(bad))
        self.assertEqual([i for i, (a, b) in enumerate(zip(good, bad)) if a != b], [position])
        observer = (directory / 'bench/window-cache-nmi/probe.s').read_text()
        self.assertIn('WRAPPER = $ff20', observer)
        self.assertIn('jmp UDEKS_NMI_ENTRY', observer)
        driver = (build / 'driver.s').read_text()
        self.assertIn('mapped:\n        jsr _udeks_nmi_drain', driver)

    def test_preserved_program_input_and_run_bindings(self):
        directory = ROOT / 'bench/artifacts' / NAME
        build = directory / 'build'
        results = ROOT / 'bench/results' / NAME
        report = json.loads((build / 'build-report.json').read_text())
        for key, root in (('source_sha256', directory), ('linked_sha256', build), ('program_sha256', build)):
            for name, sha in report[key].items():
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), sha, name)
        for root in (directory, results):
            for line in (root / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), sha, name)
        for engine in ('1986', 'vice'):
            run = json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(run['program_sha256'], report['program_sha256'])
            for case in (0, 1, 'no-pending'):
                path = results / f'{engine}-{case}.bin'
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), run['raw_sha256'][path.name])
                facts = decode(path.read_bytes(), case) if isinstance(case, int) else negative(path.read_bytes())
                self.assertEqual(facts, run['decoded'][str(case)])

# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import storage_window_probe as probe


class StorageWindow(unittest.TestCase):
    def record(self, vic=0):
        return bytes.fromhex('5357494e01020080d700a90080000000')+bytes((9|vic, 9|vic, 0x7e, 0xff, 0xa5))+bytes(11)

    def test_decoder_checks_both_vic_bank_selections(self):
        for vic in (0, 64):
            result = probe.decode(self.record(vic), vic)
            self.assertEqual(result['hidden_nmis']+result['visible_nmis'], 384)
            self.assertEqual(result['boundary_nmis'], 128)

    def test_every_record_byte_is_checked(self):
        good = self.record()
        for i in range(32):
            bad = bytearray(good); bad[i] ^= 1
            with self.subTest(i=i), self.assertRaises(ValueError): probe.decode(bad, 0)
        with self.assertRaises(ValueError): probe.decode(good[:-1], 0)

    def test_negative_patch_is_exact_and_rejects_ambiguity(self):
        data = bytes.fromhex('00288df5ffa9008d407000')
        changed = probe.negative_image(data)
        self.assertEqual([i for i, (a, b) in enumerate(zip(data, changed)) if a != b], [2])
        with self.assertRaises(ValueError): probe.negative_image(b'')
        with self.assertRaises(ValueError): probe.negative_image(data+data)

    def inputs(self):
        directory = ROOT/'bench/artifacts'/probe.EVIDENCE
        segments = probe.map_segments((directory/'module.map').read_text())
        blobs = {n: (directory/(n+'.bin')).read_bytes() for n in ('module', 'policy', 'driver', 'hidden')}
        return segments, blobs

    def test_actual_linked_candidate_fits_without_borrowing_other_reservations(self):
        result = probe.placement(*self.inputs())
        self.assertEqual({k: v['free'] for k, v in result.items()},
                         dict(module=12, policy=94, driver=346, hidden=2, state=42))
        self.assertEqual(result['hidden']['end'], 0xfefe)

    def test_overflow_gap_and_binary_map_drift_are_rejected(self):
        segments, blobs = self.inputs()
        for name in ('CODE', 'STORAGECODE', 'IECCODE', 'STORAGEHIGH', 'BSS'):
            bad = copy.deepcopy(segments)
            first, last, size = bad[name]
            bad[name] = first, last+1024, size+1024
            with self.subTest(name=name), self.assertRaises(ValueError): probe.placement(bad, blobs)
        bad = dict(blobs); bad['hidden'] += b'\0'
        with self.assertRaises(ValueError): probe.placement(segments, bad)
        bad = dict(segments); bad['UNKNOWN'] = (0, 0, 1)
        with self.assertRaises(ValueError): probe.placement(bad, blobs)
        bad = dict(segments); first, last, size = bad['CODE']; bad['CODE'] = first+1, last+1, size
        with self.assertRaises(ValueError): probe.placement(bad, blobs)

    def test_preserved_emulator_results_and_exact_artifacts(self):
        artifacts = ROOT/'bench/artifacts'/probe.EVIDENCE
        for engine in ('vice', '1986'):
            report = json.loads((ROOT/'bench/results'/probe.EVIDENCE/(engine+'.json')).read_text())
            self.assertEqual(report['engine'], engine)
            for name, expected in report['artifacts'].items():
                self.assertEqual(hashlib.sha256((artifacts/name).read_bytes()).hexdigest(), expected)
            self.assertEqual(report['layout'], probe.placement(*self.inputs()))
            self.assertEqual(len(report['records']), 3)
            for index, vic in enumerate((0, 64)):
                item = report['records'][index]
                self.assertEqual(probe.decode(bytes.fromhex(item['raw']), vic), item['decoded'])
            bad = bytes.fromhex(report['records'][2]['raw'])
            self.assertEqual(bad[:7], b'SWIN\x01\x80\x01')
            with self.assertRaises(ValueError): probe.decode(bad, 0)
        self.assertEqual(probe.negative_image((artifacts/'probe.prg').read_bytes()),
                         (artifacts/'no-forward.prg').read_bytes())

    def test_no_fake_caller_enabled_in_production(self):
        config = (ROOT/'cfg/8502-storage.cfg').read_text()
        self.assertIn('STORAGEHIGH', config)
        rules = (ROOT/'mk/storage.mk').read_text().splitlines()
        objects = next(s for s in rules if s.startswith('STORAGE_OBJECTS :='))
        self.assertNotIn('WRITE_', objects)
        self.assertNotIn('no-caller', objects)
        self.assertIn('iec_context', objects)


if __name__ == '__main__': unittest.main()

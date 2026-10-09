# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import storage_lease_probe as probe


class StorageLease(unittest.TestCase):
    def inputs(self):
        directory = ROOT/'bench/artifacts'/probe.EVIDENCE
        return directory, probe.map_segments((directory/'module.map').read_text()), {
            n: (directory/n).read_bytes() for n in probe.BLOBS if n.endswith('.bin')}

    def report(self, name):
        return json.loads((ROOT/'bench/results'/probe.EVIDENCE/(name+'.json')).read_text())

    def test_actual_service_fits_all_reservations_including_snapshots(self):
        _, segments, blobs = self.inputs()
        sizes = probe.layout(segments, blobs)
        self.assertEqual({n: v['free'] for n, v in sizes.items()},
                         dict(module=21, policy=141, driver=175, hidden=2, state=0))
        self.assertEqual(segments['BSS'], (0xe000, 0xe17f, 384))
        self.assertEqual(blobs['module.bin'][3:9], b'UIEC\x00\x02')
        for offset in (0, 9, 12): self.assertEqual(blobs['module.bin'][offset], 0x4c)

    def test_layout_rejects_gaps_overflow_and_changed_binary(self):
        _, segments, blobs = self.inputs()
        for segment in ('CODE', 'STORAGECODE', 'IECCODE', 'STORAGEHIGH', 'BSS'):
            bad = dict(segments); start, end, size = bad[segment]
            bad[segment] = start, end+256, size+256
            with self.subTest(segment=segment), self.assertRaises(ValueError): probe.layout(bad, blobs)
        bad = dict(segments); start, end, size = bad['CODE']; bad['CODE'] = start+1, end+1, size
        with self.assertRaises(ValueError): probe.layout(bad, blobs)
        bad = dict(blobs); bad['driver.bin'] += b'\x00'
        with self.assertRaises(ValueError): probe.layout(segments, bad)
        bad = dict(segments); bad['EXTRA'] = (0, 0, 1)
        with self.assertRaises(ValueError): probe.layout(bad, blobs)
        bad = dict(segments); bad['ZEROPAGE'] = (3, 0x1c, 0x1a)
        with self.assertRaises(ValueError): probe.layout(bad, blobs)

    def test_every_record_byte_and_length_is_checked(self):
        for vic in (0, 64):
            record = bytes.fromhex(self.report('1541-vic'+str(vic//64))['record'])
            probe.decode(record, vic)
            for i in range(32):
                bad = bytearray(record); bad[i] ^= 1
                with self.subTest(vic=vic, byte=i), self.assertRaises(ValueError): probe.decode(bad, vic)
            with self.assertRaises(ValueError): probe.decode(record[:-1], vic)

    def test_preserved_actual_service_runs_on_all_formats_and_both_vic_banks(self):
        directory, segments, blobs = self.inputs()
        for drive in ('1541', '1571', '1581'):
            for vic in (0, 64):
                report = self.report(drive+'-vic'+str(vic//64))
                self.assertEqual((report['drive'], report['vic'], report['negative']), (drive, vic, False))
                self.assertEqual(report['decoded'], probe.decode(bytes.fromhex(report['record']), vic))
                self.assertEqual(report['layout'], probe.layout(segments, blobs))
                self.assertEqual({n: bytes.fromhex(data) for n, data in report['files'].items()},
                                 {'KEEP': probe.KEEP, 'LEASE': bytes(range(51)), 'EMPTY': b''})
                self.assertIn('3.10', report['vice'])
                for name, digest in report['artifacts'].items():
                    self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(), digest)

    def test_negative_removes_exactly_one_real_service_instruction(self):
        directory, _, blobs = self.inputs()
        program = (directory/'probe.prg').read_bytes()
        negative = probe.negative_image(program, blobs['driver.bin'])
        self.assertEqual(negative, (directory/'no-forward.prg').read_bytes())
        changes = [(a, b) for a, b in zip(program, negative) if a != b]
        self.assertEqual(changes, [(0x8d, 0x2c)])
        for bad in (b'', program+program):
            with self.assertRaises(ValueError): probe.negative_image(bad, blobs['driver.bin'])

    def test_negative_is_observed_before_any_disk_mutation(self):
        directory, _, _ = self.inputs()
        report = self.report('1541-vic0-no-forward')
        record = bytes.fromhex(report['record'])
        self.assertTrue(report['negative'])
        self.assertEqual(report['decoded'], probe.decode_negative(record, 0))
        self.assertEqual(report['disk_before'], report['disk_after'])
        self.assertEqual(report['files'], {'KEEP': probe.KEEP.hex()})
        for name, digest in report['artifacts'].items():
            self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(), digest)
        with self.assertRaises(ValueError): probe.decode(record, 0)
        for i in range(32):
            bad = bytearray(record); bad[i] ^= 1
            with self.subTest(byte=i), self.assertRaises(ValueError): probe.decode_negative(bad, 0)

    def test_real_entry_restores_common_before_reading_private_pending(self):
        source = (ROOT/'src/services/filesystem/iec_lease.s').read_text()
        exit_code = source.split('_udeks_storage_lease_leave:', 1)[1].split('merged:', 1)[0]
        self.assertLess(exit_code.index('sta $d506'), exit_code.index('lda _udeks_storage_lease_pending'))
        self.assertLess(exit_code.index('sta NMI_PENDING'), exit_code.index('sta _udeks_storage_lease_pending'))
        self.assertNotIn('sta NMI_PENDING', source.split('prepared:', 1)[1].split('restore:', 1)[0])
        self.assertIn('sta _udeks_storage_request,x', source)
        self.assertIn('sta REQUEST,x', source)

    def test_production_uses_context_wrapper_for_public_writes(self):
        rules = (ROOT/'mk/storage.mk').read_text()
        objects = next(line for line in rules.splitlines() if line.startswith('STORAGE_OBJECTS :='))
        self.assertIn('iec_lease', objects)
        self.assertIn('iec_context', objects)
        self.assertIn('cbm_write', objects)
        self.assertIn('UDEKS_TASK_REQUEST_ABI_MINOR     20u', (ROOT/'include/udeks/task_request.h').read_text())


if __name__ == '__main__': unittest.main()

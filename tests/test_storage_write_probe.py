# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import storage_write_probe as probe
import build_d71
import build_d81


class WriteProbe(unittest.TestCase):
    def test_fresh_test_images_contain_only_the_sentinel(self):
        for drive, size in (('1541', 174848), ('1571', 349696), ('1581', 819200)):
            image = probe.make_disk(drive)
            self.assertEqual(len(image), size)
            self.assertEqual(probe.read_files(image, drive), {'KEEP': probe.KEEP})

    def test_samples_are_counted_binary_with_sector_and_chunk_boundaries(self):
        files = probe.samples()
        self.assertEqual(tuple(map(len, files.values())), probe.LENGTHS)
        self.assertTrue({1, 23, 24, 253, 254, 255, 256, 508, 515} <= set(probe.LENGTHS))
        self.assertEqual(set(files['WRTEST09']), set(range(256)))
        # Empty-file DOS behavior is a separate diagnostic, never a false pass.
        self.assertNotIn(0, probe.LENGTHS)

    def test_independent_verifier_rejects_unclosed_files(self):
        for drive, start, offset in (('1541', (18, 1), build_d71.sector_offset),
                                     ('1581', (40, 3), build_d81.sector_offset)):
            image = bytearray(probe.make_disk(drive))
            image[offset(*start)+2] = 1  # splat SEQ
            with self.assertRaises(AssertionError): probe.read_files(image, drive)

    def test_writer_not_in_production_module_or_driver_flags(self):
        rules = (ROOT/'mk/storage.mk').read_text().splitlines()
        objects = next(line for line in rules if line.startswith('STORAGE_OBJECTS :='))
        self.assertNotIn('cbm_write', objects)
        rule = rules.index('$(STORAGE_BUILD)/iec_slow.o: src/services/filesystem/iec_slow.s | $(STORAGE_BUILD)')
        self.assertNotIn('UDEKS_IEC_WRITE', rules[rule+1])

    def test_preserved_probe_records_and_exact_program(self):
        results = ROOT/'bench/results/2026-10-07-iec-write'
        program = ROOT/'bench/artifacts/2026-10-07-iec-write/write.prg'
        digest = hashlib.sha256(program.read_bytes()).hexdigest()
        for drive in ('1541', '1571', '1581'):
            result = json.loads((results/(drive+'.json')).read_text())
            self.assertEqual(result['drive'], drive)
            self.assertEqual(result['program_sha256'], digest)
            self.assertEqual(result['lengths'], list(probe.LENGTHS))
            records = {r['phase']: r for r in result['records']}
            protected = bytes.fromhex(records['write-protected']['record'])
            self.assertEqual(protected[0], 2)
            self.assertEqual(protected[2:4], bytes((10, 30)))
            self.assertEqual(records['write-protected']['disk_sha256'], result['before_sha256'])
            for phase in ('create-read', 'reboot-read'):
                raw = bytes.fromhex(records[phase]['record'])
                self.assertEqual(len(raw), 32)
                self.assertEqual(raw[0], 2)
                self.assertEqual(raw[12], 10)
                self.assertEqual(raw[8:10], raw[10:12])
            self.assertEqual(records['create-read']['disk_sha256'], records['reboot-read']['disk_sha256'])
            self.assertEqual(result['empty_file'], {'intended_size': 0, 'actual': '0d', 'qualified': False})


if __name__ == '__main__': unittest.main()

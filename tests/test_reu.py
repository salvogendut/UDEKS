# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from reu_probe import decode, misbanked_image


class CapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        shared = Path(cls.tmp.name)/'reu.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                        '-DUDEKS_REU_HOST_TEST', '-I'+str(ROOT/'include'),
                        str(ROOT/'src/services/memory/reu_capacity.c'),
                        str(ROOT/'bench/reu/capacity_mock.c'), '-o', str(shared)], check=True)
        cls.lib = ctypes.CDLL(str(shared))
        cls.lib.udeks_reu_discover.restype = ctypes.c_ubyte

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def byte(self, name):
        return ctypes.c_ubyte.in_dll(self.lib, name)

    def word(self, name):
        return ctypes.c_uint.in_dll(self.lib, name)

    def reset(self, banks):
        self.byte('mock_banks').value = banks
        self.byte('mock_unbacked').value = 0
        self.byte('mock_latch').value = 0x69
        self.byte('mock_fail_after_write').value = 0
        self.byte('udeks_reu_capacity_banks').value = 8
        for name in ('mock_calls', 'mock_fail', 'mock_corrupt'):
            self.word(name).value = 0
        self.ram = (ctypes.c_ubyte*16).in_dll(self.lib, 'mock_ram')
        self.ram[:] = bytes((i*29+3)&255 for i in range(16))
        self.before = bytes(self.ram)

    def test_capacities_preserve_every_byte_and_publish_only_verified_prefix(self):
        for banks in (2, 4, 8, 16):
            with self.subTest(banks=banks):
                self.reset(banks)
                self.assertEqual(self.lib.udeks_reu_discover(), 0)
                self.assertEqual(self.byte('udeks_reu_capacity_banks').value, min(banks, 8))
                self.assertEqual(bytes(self.ram), self.before)
                self.assertEqual(self.word('mock_calls').value, 48 if banks >= 8 else 41)
                directions = (ctypes.c_ubyte*128).in_dll(self.lib, 'mock_directions')
                self.assertEqual(bytes(directions[:16]), bytes([1]*8+[0]*8))

    def test_absent_clears_old_capacity_without_writes(self):
        self.reset(0)
        self.assertEqual(self.lib.udeks_reu_discover(), 19)
        self.assertEqual(self.byte('udeks_reu_capacity_banks').value, 0)
        self.assertEqual(self.word('mock_calls').value, 1)
        self.assertEqual(bytes(self.ram), self.before)

    def test_1764_unpopulated_upper_banks_are_not_mirrors(self):
        self.reset(4)
        self.byte('mock_unbacked').value = 1
        self.assertEqual(self.lib.udeks_reu_discover(), 0)
        self.assertEqual(self.byte('udeks_reu_capacity_banks').value, 4)
        self.assertEqual(bytes(self.ram), self.before)

    def test_unknown_alias_geometries_rejected_and_restored(self):
        for banks in (1, 3, 5, 6, 7):
            with self.subTest(banks=banks):
                self.reset(banks)
                self.assertEqual(self.lib.udeks_reu_discover(), 5)
                self.assertEqual(self.byte('udeks_reu_capacity_banks').value, 0)
                self.assertEqual(bytes(self.ram), self.before)

    def test_each_transfer_failure_keeps_device_offline(self):
        for after in (0, 1):
            for call in range(1, 49):
                with self.subTest(call=call, after=after):
                    self.reset(8)
                    self.word('mock_fail').value = call
                    self.byte('mock_fail_after_write').value = after
                    self.assertEqual(self.lib.udeks_reu_discover(), 5)
                    self.assertEqual(self.byte('udeks_reu_capacity_banks').value, 0)
                    # A failed restoring write may leave damaged data; never
                    # claim atomic recovery from a broken device. Other
                    # injected single failures must restore all preimages.
                    if after or not 33 <= call <= 40:
                        self.assertEqual(bytes(self.ram), self.before)

    def test_corrupt_geometry_or_restoration_read_cannot_publish_capacity(self):
        for call in (17, 18, 20, 22, 24, 26, 28, 30, 32):
            with self.subTest(call=call):
                self.reset(8)
                self.word('mock_corrupt').value = call
                self.assertEqual(self.lib.udeks_reu_discover(), 5)
                self.assertEqual(self.byte('udeks_reu_capacity_banks').value, 0)
                self.assertEqual(bytes(self.ram), self.before)
        for call in range(41, 49):
            self.reset(8)
            self.word('mock_corrupt').value = call
            self.assertEqual(self.lib.udeks_reu_discover(), 5)
            self.assertEqual(self.byte('udeks_reu_capacity_banks').value, 0)


def record(banks):
    data = bytearray(32)
    data[:8] = b'REUQ\x01\x02\x00'+bytes([banks])
    data[8:10] = (128 if banks else 0).to_bytes(2, 'little')
    data[10:12] = (265+3*banks if banks else 1).to_bytes(2, 'little')
    data[12:17] = bytes((8, banks, min(banks, 8), 0, banks)) if banks else bytes((0, 0, 0, 19, 0))
    return data


class RecordTests(unittest.TestCase):
    def test_exact_matrix(self):
        for banks in (0, 2, 4, 8, 16):
            self.assertEqual(decode(record(banks), banks)['usable_prefix_kib'], min(banks, 8)*64)

    def test_incomplete_failure_and_false_coverage_rejected(self):
        for offset in range(32):
            data = record(8)
            data[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                decode(data, 8)

    def test_bad_config_and_size_rejected(self):
        for size in (0, 31, 33):
            with self.assertRaises(ValueError):
                decode(bytes(size), 8)
        with self.assertRaises(ValueError):
            decode(record(8), 4)

    def test_fault_patch_is_unique_and_changes_only_bank_bit(self):
        original = bytes.fromhex('a90009408d06d560')
        modified = misbanked_image(original)
        self.assertEqual(modified, bytes.fromhex('a90009008d06d560'))
        for invalid in (b'', original*2):
            with self.assertRaises(ValueError):
                misbanked_image(invalid)


class EvidenceTests(unittest.TestCase):
    def test_preserved_records_images_and_source_hashes(self):
        folder = ROOT/'bench/results/2026-10-09-reu'
        report = json.loads((folder/'report.json').read_text())
        for name, expected in report['source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), expected, name)
        for name, expected in report['artifact_sha256'].items():
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(), expected, name)
        self.assertEqual((folder/'misbanked.prg').read_bytes(),
                         misbanked_image((folder/'probe.prg').read_bytes()))
        self.assertEqual([r['case'] for r in report['records']],
                         ['vice-0', 'vice-128', 'vice-256', 'vice-512', 'vice-1024', 'misbanked'])
        for item in report['records']:
            raw = (folder/(item['case']+'.bin')).read_bytes()
            self.assertEqual(raw.hex(), item['raw'])
            if item['case'] == 'misbanked':
                self.assertEqual(raw[:7], b'REUQ\x01\x80\x0a')
                with self.assertRaises(ValueError):
                    decode(raw, 8)
            else:
                banks = int(item['case'].split('-')[1])//64
                self.assertEqual(decode(raw, banks), item['decoded'])

    def test_preserved_checksums(self):
        folder = ROOT/'bench/results/2026-10-09-reu'
        listed = set()
        for line in (folder/'SHA256SUMS').read_text().splitlines():
            expected, name = line.split('  ', 1)
            self.assertNotIn(name, listed)
            listed.add(name)
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(), expected, name)
        required = {p.name for p in folder.iterdir() if p.suffix in ('.prg', '.map', '.bin', '.json', '.log')}
        self.assertEqual(listed, required)


if __name__ == '__main__':
    unittest.main()

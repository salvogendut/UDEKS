# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from build_d71 import blank_d71, d64_compatibility_image, mark_used, sector_offset
from build_udex import build_executable
from disk_exec_fixture import build_fixture


class DiskExecFixture(unittest.TestCase):
    def setUp(self):
        self.program = build_executable(b'\xa9\x2a\x60', cpu=1,
            load_address=0x200, entry_address=0x200, bss_size=3)

    def test_real_files_preserve_exact_udex_without_prg_prefix(self):
        base = blank_d71()
        base[:256] = b'B'*256  # owned boot payload must never be allocated
        mark_used(base, 1, 0)
        for image in (base, d64_compatibility_image(base)):
            original = bytes(image)
            result = build_fixture(image, self.program)
            self.assertEqual(bytes(image), original)
            self.assertEqual(len(result), len(image))
            self.assertEqual(result[:256], original[:256])
            for slot, (name, expected) in enumerate((('DISKCOW', self.program),
                    ('BADUDEX', b'NOT A UDEX FILE\n'), ('SHORT', self.program[:-1]))):
                entry = sector_offset(18, 1)+2+slot*32
                self.assertEqual(result[entry], 0x81)
                self.assertEqual(result[entry+3:entry+19].rstrip(b'\xa0'), name.encode())
                sector = sector_offset(result[entry+1], result[entry+2])
                self.assertEqual(result[sector:sector+2], bytes((0, len(expected)+1)))
                self.assertEqual(result[sector+2:sector+2+len(expected)], expected)

    def test_positive_fixture_rejects_bad_header_and_size(self):
        for offset, value in ((0, 0), (4, 1), (6, 2), (7, 2), (9, 3),
                              (10, 4), (13, 10), (15, 1)):
            bad = bytearray(self.program); bad[offset] = value
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                build_fixture(blank_d71(), bad)
        for bad in (b'', self.program[:-1], self.program+b'x'):
            with self.assertRaises(ValueError): build_fixture(blank_d71(), bad)

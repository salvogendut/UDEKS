# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from add_disk_apps import add_apps, directory_names
from build_d71 import blank_d71, d64_compatibility_image, install_prg_file, sector_offset
from managed_app_fixture import dos_file
from xcalc_probe import pointer_test_scratch


class GenericPackaging(unittest.TestCase):
    program = b'UDEX\0\x02\x01\0\0\x10\x01\0\0\0\0\x10\x60\0\0'

    def test_both_formats_install_exact_stream_without_changing_existing_files(self):
        original = blank_d71()
        install_prg_file(original, 'EXISTING.BIN', self.program, file_type=0x81)
        for disk in (original, d64_compatibility_image(original)):
            before = bytes(disk)
            image = add_apps(disk, [('HELLO.BIN', self.program), ('second.bin', self.program)])
            self.assertEqual(bytes(disk), before)
            self.assertEqual(len(image), len(before))
            for name in ('HELLO', 'SECOND', 'EXISTING'):
                _, offsets = dos_file(image, name)
                self.assertEqual(bytes(image[i] for i in offsets), self.program)
            self.assertEqual(image[:256], before[:256])  # boot sector intact

    def test_collisions_names_and_bad_streams_are_rejected_without_mutation(self):
        disk = blank_d71()
        install_prg_file(disk, 'EXISTING.BIN', b'PRG', file_type=0x82)
        original = bytes(disk)
        cases = [[('existing.bin', self.program)],
                 [('x.bin', self.program), ('X.BIN', self.program)],
                 [('TOOLONGTOOLONG.BIN', self.program)],
                 [('../X.BIN', self.program)], [('X.ETC', self.program)],
                 [('X.BIN', b'not an executable')]]
        for files in cases:
            with self.assertRaises(ValueError): add_apps(disk, files)
            self.assertEqual(bytes(disk), original)

    def test_directory_validation_and_multiple_sectors(self):
        disk = blank_d71()
        for i in range(10): install_prg_file(disk, f'A{i}.BIN', self.program, file_type=0x81)
        self.assertEqual(len(directory_names(disk)), 10)
        with self.assertRaises(ValueError): directory_names(disk[:-1])
        second = disk[sector_offset(18, 1)+1]
        disk[sector_offset(18, second):sector_offset(18, second)+2] = bytes((18, 1))
        with self.assertRaisesRegex(ValueError, 'cyclic'): directory_names(disk)

    def test_cli_will_not_overwrite_input_or_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            disk = Path(tmp)/'disk.d64'; app = Path(tmp)/'HELLO.BIN'
            disk.write_bytes(d64_compatibility_image(blank_d71()))
            app.write_bytes(self.program); before = disk.read_bytes()
            result = subprocess.run([sys.executable, str(ROOT/'tools/add_disk_apps.py'),
                '--disk', str(disk), '--output', str(disk), str(app)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(disk.read_bytes(), before)

    def test_pointer_probe_uses_only_map_proven_padding(self):
        text = 'Segment list:\nGRAPHICSHELP 00A100 00A1D7 0000D8 00001\nVICSHADOW 00A1E0 00C11F 001F40 00001\n\nExports list by name:\n'
        self.assertEqual(pointer_test_scratch(text), 0xa1d8)
        with self.assertRaises(ValueError): pointer_test_scratch(text.replace('00A1D7', '00A1DD'))


if __name__ == '__main__': unittest.main()

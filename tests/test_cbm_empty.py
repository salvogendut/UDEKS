# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate the only raw write: length byte of our newly created empty file."""
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EIO = 5


class EmptyFinalizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        output = Path(cls.temp.name)/'empty.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', '-DUDEKS_IEC_WRITE', '-I'+str(ROOT/'include'),
                        str(ROOT/'src/services/filesystem/cbm_file.c'),
                        str(ROOT/'tests/fixtures/storage_transport.c'), '-o', str(output)], check=True)
        cls.lib = c.CDLL(str(output))
        cls.lib.udeks_cbm_finish_empty.argtypes = [c.c_uint8, c.c_char_p]
        cls.lib.udeks_cbm_finish_empty.restype = c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def byte(self, name): return c.c_uint8.in_dll(self.lib, 'test_'+name)
    def word(self, name): return c.c_uint16.in_dll(self.lib, 'test_'+name)

    def setUp(self):
        self.lib.udeks_cbm_close()
        for name in ('open_error', 'close_error', 'open_count', 'close_count',
                     'dos_error', 'status_bad', 'status_error', 'talk_error', 'command_error',
                     'fail_command', 'listen_error', 'send_error', 'unlisten_error',
                     'ignore_update', 'update_error'):
            self.byte(name).value = 0
        for name in ('update_count', 'send_count', 'sent_value', 'pointer_count'):
            self.word(name).value = 0
        self.word('fail_at').value = 65535
        self.sectors = (c.c_uint16*16384).in_dll(self.lib, 'test_sectors')
        self.sectors[:] = [0]*16384
        self.tracks = (c.c_uint8*64).in_dll(self.lib, 'test_tracks')
        self.numbers = (c.c_uint8*64).in_dll(self.lib, 'test_numbers')
        self.units = (c.c_uint8*64).in_dll(self.lib, 'test_units')
        self.tracks[:] = self.numbers[:] = self.units[:] = bytes(64)
        self.directory = bytearray(b'\0\xff'+bytes(254))
        self.entry(0, b'TARGET', 1, 0)
        self.entry(1, b'KEEP', 1, 1)
        self.disk = {(18, 0): bytearray(b'\x12\x01\x41\0'+bytes(252)),
                     (18, 1): self.directory,
                     (1, 0): bytearray(b'\0\2\r'+bytes(i % 256 for i in range(253))),
                     (1, 1): bytearray(b'\0\2\r'+bytes([0x5a]*253))}
        self.sync()

    def entry(self, slot, name, track, sector):
        p = 2+slot*32
        self.directory[p:p+30] = bytes((0x81, track, sector))+name.ljust(16, b'\xa0')+bytes(9)+b'\1\0'

    def sync(self):
        for i, ((track, sector), data) in enumerate(self.disk.items()):
            self.tracks[i], self.numbers[i] = track, sector
            self.sectors[i*256:(i+1)*256] = data

    def run_finalizer(self, name=b'TARGET'):
        return self.lib.udeks_cbm_finish_empty(8, name.ljust(16, b'\xa0'))

    def rejected(self):
        before = list(self.sectors)
        self.assertEqual(self.run_finalizer(), EIO)
        self.assertEqual(list(self.sectors), before)
        self.assertEqual(self.word('update_count').value, 0)

    def test_exactly_one_byte_changes_and_other_files_directory_bam_stay_intact(self):
        before = list(self.sectors)
        self.assertEqual(self.run_finalizer(), 0)
        changed = [i for i, (a, b) in enumerate(zip(before, self.sectors)) if a != b]
        self.assertEqual(changed, [2*256+1])
        self.assertEqual((before[513], self.sectors[513]), (2, 1))
        self.assertEqual(self.word('update_count').value, 1)
        self.assertEqual(self.word('send_count').value, 1)
        self.assertEqual(self.word('sent_value').value, 0x101)
        self.assertEqual(self.byte('close_count').value, 1)

    def test_d81_geometry_uses_same_length_rule_without_touching_its_bam(self):
        del self.disk[18, 0]; del self.disk[18, 1]
        self.disk[40, 0] = bytearray(b'\x28\3D\0'+bytes(252))
        self.disk[40, 3] = self.directory
        self.tracks[:] = bytes(64); self.sync()
        before = list(self.sectors)
        self.assertEqual(self.run_finalizer(), 0)
        changed = [i for i, (a, b) in enumerate(zip(before, self.sectors)) if a != b]
        self.assertEqual(changed, [1])

    def test_already_empty_block_needs_no_write(self):
        self.disk[1, 0][1] = 1; self.sync()
        before = list(self.sectors)
        self.assertEqual(self.run_finalizer(), 0)
        self.assertEqual(list(self.sectors), before)
        self.assertEqual(self.word('pointer_count').value, 0)
        self.assertEqual(self.word('update_count').value, 0)

    def test_missing_name_and_case_mismatch_never_write(self):
        for name in (b'NOTHERE', b'target'):
            before = list(self.sectors)
            self.assertEqual(self.run_finalizer(name), EIO)
            self.assertEqual(list(self.sectors), before)
            self.assertEqual(self.word('update_count').value, 0)

    def test_duplicate_match_and_cross_link_before_or_after_match_fail(self):
        for earlier in (False, True):
            for name in (b'TARGET', b'ALIAS'):
                self.setUp()
                self.entry(0 if earlier else 1, name, 1, 0)
                self.entry(1 if earlier else 0, b'TARGET', 1, 0)
                self.sync(); self.rejected()

    def test_splat_locked_wrong_type_and_multiple_blocks_fail(self):
        for field, value in ((0, 1), (0, 0xc1), (0, 0xc2), (0, 0x83), (0, 0x84),
                             (28, 0), (28, 2), (29, 1)):
            self.setUp(); self.directory[2+field] = value
            self.sync(); self.rejected()

    def test_closed_prg_empty_file_has_same_exact_length_fix(self):
        self.directory[2]=0x82;self.sync()
        before=list(self.sectors)
        self.assertEqual(self.run_finalizer(),0)
        self.assertEqual([i for i,(a,b) in enumerate(zip(before,self.sectors)) if a!=b],[513])

    def test_reserved_or_invalid_sector_targets_fail(self):
        for track, sector in ((0, 0), (18, 0), (18, 1), (53, 0), (71, 0), (1, 21)):
            self.setUp(); self.entry(0, b'TARGET', track, sector)
            self.sync(); self.rejected()

    def test_non_cr_nonempty_or_multiblock_data_never_modified(self):
        for prefix in (b'\0\2A', b'\0\3\r', b'\1\2\r', b'\0\0\r'):
            self.setUp(); self.disk[1, 0][:3] = prefix
            self.sync(); self.rejected()

    def test_early_eoi_and_read_errors_never_write(self):
        for position in (2, 3, 127, 254):
            self.setUp(); self.sectors[512+position] |= 0x100
            self.rejected()
        self.setUp(); self.word('fail_at').value = 100
        self.rejected()

    def test_directory_error_after_match_does_not_modify_provisional_target(self):
        self.directory[:2] = b'\x12\2'  # missing next directory sector
        self.sync(); self.rejected()

    def test_cyclic_directory_is_bounded_and_cannot_write(self):
        self.directory[:2] = b'\x12\1'
        self.sync(); self.rejected()

    def test_transport_and_dos_failures_do_not_issue_update(self):
        for name, value in (('open_error', 3), ('dos_error', 26), ('status_bad', 1),
                            ('status_error', 2), ('talk_error', 2), ('listen_error', 2),
                            ('send_error', 2), ('unlisten_error', 2), ('fail_command', 2),
                            ('fail_command', 3)):
            self.setUp(); self.byte(name).value = value
            self.rejected()

    def test_update_error_or_ignored_update_is_not_success(self):
        for field in ('update_error', 'ignore_update'):
            self.setUp(); self.byte(field).value = 1
            before = list(self.sectors)
            self.assertEqual(self.run_finalizer(), EIO)
            self.assertEqual(self.word('update_count').value, 1)
            self.assertEqual(list(self.sectors), before)

    def test_close_error_after_update_is_still_an_error_not_rollback(self):
        self.byte('close_error').value = 2
        self.assertEqual(self.run_finalizer(), EIO)
        self.assertEqual(self.sectors[513], 1)
        self.assertEqual(self.word('update_count').value, 1)


if __name__ == '__main__': unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_d81


class StorageService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        library = Path(cls.temp.name) / 'storage.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', '-DUDEKS_STORAGE_HOST_TEST', '-DUDEKS_FS_READ_ONLY', '-I'+str(ROOT/'include'),
                        str(ROOT/'src/services/filesystem/iec_service.c'),
                        str(ROOT/'src/services/filesystem/fs_namespace.c'),
                        str(ROOT/'src/services/filesystem/cbm_file.c'),
                        str(ROOT/'tests/fixtures/storage_transport.c'),
                        '-o', str(library)], check=True)
        cls.lib = c.CDLL(str(library))
        cls.lib.udeks_storage_dispatch.restype = c.c_uint8

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.lib.udeks_cbm_close()
        self.lib.udeks_storage_reset()
        self.r = (c.c_uint8 * 38).in_dll(self.lib, 'udeks_storage_request')
        for name in ('open_error', 'close_error', 'open_count', 'close_count',
                     'dos_error', 'status_bad', 'status_error', 'talk_error', 'command_error'):
            self.byte(name).value = 0
        self.word('fail_at').value = 65535
        self.tracks = (c.c_uint8 * 64).in_dll(self.lib, 'test_tracks')
        self.units = (c.c_uint8 * 64).in_dll(self.lib, 'test_units')
        self.units[:] = bytes(64)
        self.numbers = (c.c_uint8 * 64).in_dll(self.lib, 'test_numbers')
        self.sectors = (c.c_uint16 * 16384).in_dll(self.lib, 'test_sectors')
        self.disk = {(18, 1): bytearray(b'\0\xff'+bytes(254))}
        self.sync()

    def byte(self, name): return c.c_uint8.in_dll(self.lib, 'test_'+name)
    def word(self, name): return c.c_uint16.in_dll(self.lib, 'test_'+name)

    def sync(self):
        self.tracks[:] = bytes(64)
        for i, ((track, sector), data) in enumerate(self.with_header(self.disk).items()):
            self.tracks[i], self.numbers[i] = track, sector
            self.sectors[i*256:(i+1)*256] = data

    @staticmethod
    def with_header(disk):
        if (40,0) in disk or (18,0) in disk: return disk
        return dict(disk) | {(18,0): bytearray(b'\x12\x01\x41\0'+bytes(252))}

    def file(self, data, name=b'HELLO', slot=0, first=0):
        blocks = max(1, (len(data)+253)//254)
        directory = self.disk[18, 1]
        offset = 2+slot*32
        directory[offset:offset+19] = bytes((0x81, 1, first))+name.ljust(16, b'\xa0')
        directory[offset+28:offset+30] = blocks.to_bytes(2, 'little')
        for i in range(blocks):
            part = data[i*254:(i+1)*254]
            link = bytes((1, first+i+1)) if i+1 < blocks else bytes((0, len(part)+1))
            self.disk[1, first+i] = bytearray(link+part.ljust(254, b'\0'))
        self.sync()

    def request(self, op, payload=b'', fd=0, count=None, flags=0, minor=5):
        self.r[:] = bytes(38)
        self.r[:6] = b'UTRQ\0\5'
        self.r[5] = minor
        self.r[6:14] = (1, op, 73, fd, len(payload) if count is None else count, 0, 0, flags)
        self.r[14:14+len(payload)] = payload
        handled = self.lib.udeks_storage_dispatch()
        return handled, self.r[6], self.r[11], self.r[12]

    def mount(self): self.assertEqual(self.request(17, b'\x08/mnt'), (1, 2, 0, 0))

    def read_all(self):
        data = bytearray()
        for _ in range(100):
            handled, state, n, error = self.request(1, fd=4, count=24)
            self.assertEqual((handled, state, error), (1, 2, 0))
            if not n: return bytes(data)
            data.extend(self.r[14:14+n])
        self.fail('file did not end')

    def test_mount_unmount_and_no_device_retry(self):
        self.byte('open_error').value = 3
        self.assertEqual(self.request(17, b'\x08/mnt'), (1, 128, 0, 19))
        self.byte('open_error').value = 0
        self.mount()
        self.assertEqual(self.request(17, b'\x09/mnt'), (1, 128, 0, 16))
        self.assertEqual(self.request(18, b'/mnt'), (1, 2, 0, 0))
        self.assertEqual(self.request(18, b'/mnt'), (1, 128, 0, 2))

    def test_validation_precedes_io(self):
        for payload, fd, flags in ((b'\x07/mnt', 0, 0), (b'\x08/bad', 0, 0),
                                   (b'\x08/mnt', 1, 0), (b'\x08/mnt', 0, 1)):
            self.assertEqual(self.request(17, payload, fd, flags=flags), (1, 128, 0, 22))
        self.assertEqual(self.byte('open_count').value, 0)
        self.mount()

    def test_mount_requires_minor_five(self):
        self.request(17, b'\x08/mnt', flags=1)
        self.r[5] = 4
        self.assertEqual(self.lib.udeks_storage_dispatch(), 1)
        self.assertEqual(self.r[12], 38)
        self.assertEqual(self.byte('open_count').value, 0)

    def test_bootfs_and_lifecycle_fall_through_unchanged(self):
        for op, payload, fd in ((6, b'/bin', 1), (6, b'/mnt-other', 1),
                                (7, b'', 3), (9, b'', 3), (16, b'', 0), (99, b'', 0)):
            self.request(op, payload, fd)
            before = bytes(self.r)
            self.assertEqual(self.lib.udeks_storage_dispatch(), 0)
            self.assertEqual(bytes(self.r), before)

    def test_directory_entries_eof_close_and_small_buffer(self):
        self.file(b'hi')
        self.file(b'bye', b'LONG FILE NAME.', slot=1, first=1)
        self.mount()
        self.assertEqual(self.request(6, b'/mnt', 1), (1, 2, 4, 0))
        self.assertEqual(self.request(18, b'/mnt'), (1, 128, 0, 16))
        self.assertEqual(self.request(6, b'/mnt', 1), (1, 128, 0, 24))
        before = self.word('position').value
        self.assertEqual(self.request(7, fd=4, count=17), (1, 128, 0, 22))
        self.assertEqual(self.word('position').value, before)
        self.assertEqual(self.request(7, fd=4, count=24), (1, 2, 7, 0))
        self.assertEqual(bytes(self.r[16:21]), b'HELLO')
        self.assertEqual(self.request(7, fd=4, count=24), (1, 2, 17, 0))
        for _ in range(2): self.assertEqual(self.request(7, fd=4, count=24), (1, 2, 0, 0))
        self.assertEqual(self.request(9, fd=4), (1, 2, 0, 0))
        self.assertEqual(self.request(9, fd=4), (1, 128, 0, 9))

    def test_stat_and_read_contract(self):
        self.assertEqual(self.request(6, b'/mnt', 1), (1, 128, 0, 2))
        self.mount()
        self.assertEqual(self.request(8, b'/mnt'), (1, 2, 3, 0))
        self.assertEqual(bytes(self.r[14:17]), b'\4\0\0')
        self.request(6, b'/mnt', 1)
        self.assertEqual(self.request(1, fd=4, count=24), (1, 128, 0, 21))
        self.assertEqual(self.request(1, fd=7, count=24), (1, 128, 0, 9))

    def test_exact_empty_one_byte_boundaries_and_binary_files(self):
        for size in (0, 1, 2, 24, 253, 254, 255, 256, 508, 509, 515):
            with self.subTest(size=size):
                data = bytes(i % 256 for i in range(size))
                self.file(data); self.mount()
                self.assertEqual(self.request(6, b'/mnt/HELLO'), (1, 2, 4, 0))
                self.assertEqual(self.request(1, fd=4, count=25), (1, 128, 0, 22))
                self.assertEqual(self.request(1, fd=4, count=0), (1, 2, 0, 0))
                self.assertEqual(self.read_all(), data)
                for _ in range(2): self.assertEqual(self.request(1, fd=4, count=24), (1, 2, 0, 0))
                self.assertEqual(self.request(7, fd=4, count=24), (1, 128, 0, 20))
                self.assertEqual(self.request(18, b'/mnt'), (1, 128, 0, 16))
                self.assertEqual(self.request(9, fd=4), (1, 2, 0, 0))
                self.assertEqual(self.request(18, b'/mnt'), (1, 2, 0, 0))

    def test_missing_file_and_status_errors_leave_slot_available(self):
        self.file(b'AB'); self.mount()
        self.assertEqual(self.request(6, b'/mnt/NOFILE'), (1, 128, 0, 2))
        for field, value in (('dos_error', 74), ('status_bad', 1), ('status_error', 2),
                             ('talk_error', 2), ('command_error', 2)):
            self.byte(field).value = value
            self.assertEqual(self.request(6, b'/mnt/HELLO'), (1, 128, 0, 5))
            self.byte(field).value = 0
        self.assertEqual(self.request(6, b'/mnt/HELLO'), (1, 2, 4, 0))

    def test_bad_filenames_cannot_inject_dos_commands_or_wildcards(self):
        self.mount()
        before = self.byte('open_count').value
        for name in (b'A'*17, b'@A', b'A,W', b'A*', b'A?', b'A:B', b'A\0B', b'\xc1'):
            self.assertEqual(self.request(6, b'/mnt/'+name), (1, 128, 0, 22))
        self.assertEqual(self.request(6, b'/mnt/A/B'), (1, 128, 0, 20))
        self.assertEqual(self.byte('open_count').value, before)

    def test_partial_read_defers_io_error_and_allows_reopen(self):
        self.file(b'AB'); self.mount(); self.request(6, b'/mnt/HELLO')
        self.word('fail_at').value = 3
        self.assertEqual(self.request(1, fd=4, count=24), (1, 2, 1, 0))
        self.assertEqual(self.r[14], 65)
        for _ in range(2): self.assertEqual(self.request(1, fd=4, count=24), (1, 128, 0, 5))
        self.assertEqual(self.request(9, fd=4), (1, 2, 0, 0))
        self.word('fail_at').value = 65535
        self.request(6, b'/mnt/HELLO')
        self.assertEqual(self.read_all(), b'AB')

    def test_failed_sector_read_does_not_reuse_buffer(self):
        self.file(b'A'*255); self.mount(); self.request(6, b'/mnt/HELLO')
        del self.disk[1, 1]
        self.sync()
        content = bytearray()
        for _ in range(20):
            result = self.request(1, fd=4, count=24)
            if result[3]: break
            content.extend(self.r[14:14+result[2]])
        self.assertEqual(bytes(content), b'A'*254)
        self.assertEqual(result, (1, 128, 0, 5))

    def test_malformed_file_chains_fail_bounded(self):
        for link, count in ((b'\0\0', 1), (b'\x01\0', 1), (b'\x47\0', 2),
                            (b'\x01\x15', 2), (b'\0\x03', 2), (b'\x01\0', 2)):
            with self.subTest(link=link, count=count):
                self.setUp(); self.file(b'AB')
                self.disk[1, 0][:2] = link
                self.disk[18, 1][30:32] = count.to_bytes(2, 'little')
                self.sync(); self.mount(); self.request(6, b'/mnt/HELLO')
                for _ in range(30):
                    result = self.request(1, fd=4, count=24)
                    if result[3]: break
                self.assertEqual(result, (1, 128, 0, 5))

    def test_cyclic_directory_is_bounded(self):
        self.disk[18, 1][:2] = b'\x12\x01'
        self.sync(); self.mount(); self.request(6, b'/mnt', 1)
        self.assertEqual(self.request(7, fd=4, count=24), (1, 128, 0, 5))

    def test_no_media_mount_fails_and_retry_works(self):
        self.byte('dos_error').value = 74
        self.assertEqual(self.request(17, b'\x08/mnt'), (1, 128, 0, 5))
        self.byte('dos_error').value = 0
        self.mount()

    def test_directory_last_slot_and_second_sector(self):
        self.file(b'AB', b'LAST', slot=7)
        self.disk[18, 1][:2] = b'\x12\x02'
        second = bytearray(self.disk[18, 1])
        second[:2] = b'\0\xff'
        second[2+7*32+3:2+7*32+7] = b'NEXT'
        self.disk[18, 2] = second
        self.sync(); self.mount(); self.request(6, b'/mnt', 1)
        for name in (b'LAST', b'NEXT'):
            self.assertEqual(self.request(7, fd=4, count=24), (1, 2, 6, 0))
            self.assertEqual(bytes(self.r[16:20]), name)
        self.assertEqual(self.request(7, fd=4, count=24), (1, 2, 0, 0))

    def test_both_petscii_alphabets_and_ascii_lowercase(self):
        self.file(b'AB', bytes(x+128 for x in b'HELLO'))
        self.mount()
        self.assertEqual(self.request(6, b'/mnt/hello'), (1, 2, 4, 0))
        self.assertEqual(self.read_all(), b'AB')

    def test_directory_error_is_sticky_until_close(self):
        self.mount(); self.request(6, b'/mnt', 1)
        self.word('fail_at').value = 2
        for _ in range(2):
            self.assertEqual(self.request(7, fd=4, count=24), (1, 128, 0, 5))
        self.request(9, fd=4)
        self.word('fail_at').value = 65535
        self.request(6, b'/mnt', 1)
        self.assertEqual(self.request(7, fd=4, count=24), (1, 2, 0, 0))

    def test_unclosed_and_rel_files_are_not_sequential_files(self):
        for kind in (1, 0x84, 0xc4):
            self.setUp(); self.file(b'AB')
            self.disk[18, 1][2] = kind
            self.sync(); self.mount()
            self.assertEqual(self.request(6, b'/mnt/HELLO'), (1, 128, 0, 22))

    def test_early_sector_eoi_and_truncated_directory_are_errors(self):
        self.file(b'AB'); self.mount(); self.request(6, b'/mnt/HELLO')
        self.sectors[256+2] |= 0x100  # first data byte, not final logical byte
        self.assertEqual(self.request(1, fd=4, count=24), (1, 128, 0, 5))
        self.request(9, fd=4); self.request(6, b'/mnt', 1)
        self.sectors[2] |= 0x100
        self.assertEqual(self.request(7, fd=4, count=24), (1, 128, 0, 5))

    def test_close_failure_releases_logical_handle(self):
        self.file(b'AB'); self.mount(); self.request(6, b'/mnt/HELLO')
        self.byte('close_error').value = 2
        self.assertEqual(self.request(9, fd=4), (1, 128, 0, 5))
        self.byte('close_error').value = 0
        self.assertEqual(self.request(18, b'/mnt'), (1, 2, 0, 0))

    def bam(self, dual=False):
        bam = bytearray(256); bam[0:4] = bytes((18, 1, 65, 128 if dual else 0))
        for track in range(1, 36):
            count = 21 if track <= 17 else 19 if track <= 24 else 18 if track <= 30 else 17
            bam[4*track] = count
            if dual: bam[220+track] = count
        self.disk[18, 0] = bam; self.sync()
        return bam

    def test_statfs_counts_both_formats_excluding_directory_tracks(self):
        self.mount()
        for dual, total in ((False, 664), (True, 1328)):
            bam = self.bam(dual)
            bam[4] -= 3
            bam[72] = 0  # directory free sectors never counted
            if dual: bam[221] -= 2
            self.sync()
            self.assertEqual(self.request(19, b'/mnt', minor=6), (1, 2, 8, 0))
            self.assertEqual(bytes(self.r[14:22]), b'\0\1'+total.to_bytes(2, 'little')+
                (total-3-2*dual).to_bytes(2, 'little')+b'\x08\x01')
        self.assertEqual(self.request(18, b'/mnt'), (1, 2, 0, 0))

    def root(self):
        self.assertEqual(self.request(17, b'\x08/', minor=8), (1, 2, 0, 0))
        c.c_uint8.in_dll(self.lib, 'udeks_storage_boot_source').value = 1

    def d81(self):
        image=build_d81.blank_d81()
        self.disk={(40,s):bytearray(image[build_d81.sector_offset(40,s):
                                         build_d81.sector_offset(40,s)+256]) for s in range(4)}
        self.sync()

    def test_d81_highest_track_sector_and_exact_file_length(self):
        self.d81()
        directory=self.disk[40,3]
        directory[2:21]=b'\x81\x50\x27HELLO'+b'\xa0'*11
        directory[30:32]=b'\x01\0'
        self.disk[80,39]=bytearray(b'\0\x04ABC'+bytes(251))
        self.sync(); self.mount()
        self.assertEqual(self.request(6,b'/mnt/HELLO'),(1,2,4,0))
        self.assertEqual(self.read_all(),b'ABC')
        self.request(9,fd=4)
        self.disk[40,3][3]=81; self.sync()
        self.assertEqual(self.request(6,b'/mnt/HELLO'),(1,2,4,0))
        self.assertEqual(self.request(1,fd=4,count=24),(1,128,0,5))

    def test_d81_statfs_both_bams_errors_and_media_change(self):
        self.d81(); self.mount()
        self.disk[40,1][16]-=3
        self.disk[40,2][16]-=7
        self.sync()
        self.assertEqual(self.request(19,b'/mnt',minor=6),(1,2,8,0))
        self.assertEqual(bytes(self.r[14:22]),b'\0\1'+(3160).to_bytes(2,'little')+
                         (3150).to_bytes(2,'little')+b'\x08\x01')
        for sector,index,value in ((1,16,41),(2,16,41),(2,2,65),(2,3,0)):
            old=self.disk[40,sector][index]; self.disk[40,sector][index]=value;self.sync()
            self.assertEqual(self.request(19,b'/mnt',minor=6),(1,128,0,5))
            self.disk[40,sector][index]=old
        # Same mounted unit, changed medium: do not reuse the old geometry.
        self.disk={(18,1):bytearray(b'\0\xff'+bytes(254))};self.bam(True)
        self.assertEqual(self.request(19,b'/mnt',minor=6),(1,2,8,0))
        self.assertEqual(bytes(self.r[16:20]),(1328).to_bytes(2,'little')*2)

    def test_d81_296th_directory_slot_and_eof_do_not_wrap(self):
        self.d81()
        for s in range(3,40):
            self.disk[40,s]=bytearray(bytes((40,s+1)) if s<39 else b'\0\xff')+bytearray(254)
        pos=2+7*32
        self.disk[40,39][pos:pos+19]=b'\x81\x50\x27LAST'+b'\xa0'*12
        self.disk[40,39][pos+28:pos+30]=b'\x01\0'
        self.disk[80,39]=bytearray(b'\0\x02X'+bytes(253))
        self.sync();self.mount()
        self.assertEqual(self.entries(b'/mnt'),[b'LAST'])
        self.assertEqual(self.request(6,b'/mnt/LAST'),(1,2,4,0))
        self.assertEqual(self.read_all(),b'X')

    def test_d81_invalid_header_and_directory_loop_fail_closed(self):
        self.d81();self.disk[40,0][2]=0;self.sync()
        self.assertEqual(self.request(17,b'\x08/mnt'),(1,128,0,5))
        self.disk[40,0][2]=0x44;self.disk[40,3][:2]=bytes((40,3));self.sync()
        self.mount();self.request(6,b'/mnt',1)
        self.assertEqual(self.request(7,fd=4,count=24),(1,128,0,5))

    def entries(self, path):
        self.assertEqual(self.request(6, path, 1, minor=8), (1, 2, 4, 0))
        result = []
        for _ in range(160):
            response = self.request(7, fd=4, count=24, minor=8)
            self.assertEqual((response[0], response[1], response[3]), (1, 2, 0))
            if not response[2]: break
            result.append(bytes(self.r[16:16+self.r[15]]))
        else: self.fail('unbounded directory')
        self.assertEqual(self.request(9, fd=4, minor=8), (1, 2, 0, 0))
        return result

    def test_root_views_and_startup_config_are_real_disk_files(self):
        for slot, (name, content) in enumerate(((b'USH.BIN', b'shell'),
                (b'CAT.BIN', b'cat'), (b'RC.ETC', b'echo ready'),
                (b'TEST.SH', b'echo script'), (b'NOTES.TXT', b'notes'))):
            self.file(content, name, slot=slot, first=slot)
        self.root()
        self.assertEqual(self.entries(b'/'), [b'bin', b'etc', b'mnt', b'notes.txt'])
        self.assertEqual(self.entries(b'/bin'), [b'ush', b'cat', b'test'])
        self.assertEqual(self.entries(b'/etc'), [b'rc'])
        self.assertEqual(self.request(6, b'/etc/rc', minor=8), (1, 2, 4, 0))
        self.assertEqual(self.read_all(), b'echo ready')
        self.request(9, fd=4)
        self.assertEqual(self.request(6, b'/RC.ETC', minor=8), (1, 128, 0, 2))
        self.assertEqual(self.request(6, b'/mnt', 1, minor=8), (1, 128, 0, 19))

    def test_root_and_device_nine_are_independent_with_handle_ownership(self):
        self.file(b'SYSTEM', b'FOO.BIN')
        system = self.disk.copy()
        self.disk = {(18, 1): bytearray(b'\0\xff'+bytes(254))}
        self.file(b'DATA', b'FOO.BIN')
        data = self.disk.copy()
        self.tracks[:] = bytes(64)
        index = 0
        for unit, disk in ((8, system), (9, data)):
            for (track, sector), content in self.with_header(disk).items():
                self.units[index], self.tracks[index], self.numbers[index] = unit, track, sector
                self.sectors[index*256:(index+1)*256] = content
                index += 1
        self.root()
        self.assertEqual(self.request(17, b'\x09/mnt'), (1, 2, 0, 0))
        self.assertEqual(self.request(6, b'/bin/foo', minor=8), (1, 2, 4, 0))
        self.assertEqual(self.byte('device').value, 8)
        self.assertEqual(self.request(18, b'/mnt'), (1, 2, 0, 0))
        self.assertEqual(self.read_all(), b'SYSTEM')
        self.assertEqual(self.request(17, b'\x09/mnt'), (1, 128, 0, 16))
        self.request(9, fd=4)
        self.assertEqual(self.request(17, b'\x09/mnt'), (1, 2, 0, 0))
        self.assertEqual(self.request(6, b'/mnt/foo.bin', minor=8), (1, 2, 4, 0))
        self.assertEqual(self.byte('device').value, 9)
        self.assertEqual(self.request(18, b'/mnt'), (1, 128, 0, 16))
        self.assertEqual(self.read_all(), b'DATA')
        self.request(9, fd=4)
        self.assertEqual(self.request(18, b'/', minor=8), (1, 128, 0, 16))
        self.assertEqual(self.request(17, b'\x09/', minor=8), (1, 128, 0, 16))

    def test_cwd_relative_io_parent_and_rejection_are_consistent(self):
        self.file(b'echo ready', b'RC.ETC'); self.root()
        self.assertEqual(self.request(21, b'/etc', minor=8), (1, 2, 0, 0))
        self.assertEqual(self.request(22, minor=8), (1, 2, 4, 0))
        self.assertEqual(bytes(self.r[14:19]), b'/etc\0')
        self.assertEqual(self.request(6, b'./rc', minor=8), (1, 2, 4, 0))
        self.assertEqual(self.read_all(), b'echo ready'); self.request(9, fd=4)
        self.assertEqual(self.request(21, b'rc', minor=8), (1, 128, 0, 20))
        self.assertEqual(self.request(21, b'/missing', minor=8), (1, 128, 0, 2))
        self.assertEqual(self.request(21, b'/mnt', minor=8), (1, 128, 0, 19))
        self.assertEqual(self.request(22, minor=8), (1, 2, 4, 0))
        self.assertEqual(bytes(self.r[14:19]), b'/etc\0')
        self.request(21, b'../bin', minor=8)
        self.assertEqual(self.request(22, minor=8), (1, 2, 4, 0))
        self.assertEqual(bytes(self.r[14:19]), b'/bin\0')
        self.request(21, b'..', minor=8)
        self.assertEqual(self.request(22, minor=8), (1, 2, 1, 0))
        self.assertEqual(bytes(self.r[14:16]), b'/\0')

    def test_cwd_keeps_data_mount_busy_without_affecting_root(self):
        self.root(); self.mount()
        self.assertEqual(self.request(21, b'/mnt', minor=8), (1, 2, 0, 0))
        self.assertEqual(self.request(18, b'/mnt'), (1, 128, 0, 16))
        self.request(21, b'..', minor=8)
        self.assertEqual(self.request(18, b'/mnt'), (1, 2, 0, 0))

    def test_collisions_fail_both_open_and_listing_without_selecting_first(self):
        for first, second in ((b'FOO.BIN', b'FOO.SH'), (b'FOO.SH', b'FOO.BIN'),
                              (b'FOO.BIN', b'foo.bin')):
            self.setUp(); self.file(b'FIRST', first); self.file(b'SECOND', second, slot=1, first=1)
            self.root()
            self.assertEqual(self.request(6, b'/bin/foo', minor=8), (1, 128, 0, 17))
            self.assertEqual(self.request(6, b'/bin', 1, minor=8), (1, 2, 4, 0))
            self.assertEqual(self.request(7, fd=4, count=24), (1, 128, 0, 17))
            self.assertEqual(self.request(7, fd=4, count=24), (1, 128, 0, 17))
            self.assertEqual(self.request(9, fd=4), (1, 2, 0, 0))

    def test_exec_open_never_treats_scripts_or_configuration_as_udex(self):
        self.file(b'UDEXpretend', b'TEST.SH')
        self.file(b'UDEXpretend', b'RC.ETC', slot=1, first=1)
        self.root()
        for path in (b'/bin/test', b'/etc/rc'):
            self.assertEqual(self.request(6, path, fd=2, minor=8), (1, 128, 0, 8))
            self.assertEqual(self.request(6, path, minor=8), (1, 2, 4, 0))
            self.assertEqual(self.read_all(), b'UDEXpretend'); self.request(9, fd=4)
        self.assertEqual(self.request(6, b'/bin', fd=2, minor=8), (1, 128, 0, 21))

    def test_cwd_requests_validate_version_and_shape_without_mutation(self):
        self.root()
        for op, payload, extras, errno in ((21, b'/etc', {'minor': 7}, 38),
                (22, b'', {'minor': 7}, 38), (21, b'/etc', {'fd': 1}, 22),
                (22, b'X', {}, 22), (21, b'/etc', {'flags': 1}, 22)):
            options = dict(minor=8); options.update(extras)
            self.assertEqual(self.request(op, payload, **options), (1, 128, 0, errno))
        self.assertEqual(self.request(22, minor=8), (1, 2, 1, 0))

    def test_bootstrap_can_release_failed_root_for_recovery(self):
        self.assertEqual(self.request(17, b'\x08/', minor=8), (1, 2, 0, 0))
        self.assertEqual(self.request(18, b'/', minor=8), (1, 2, 0, 0))
        self.assertEqual(self.request(6, b'/bin', 1, minor=8)[0], 0)
        self.assertEqual(self.request(21, b'/bin', minor=8), (1, 2, 0, 0))

    def test_statfs_validates_before_io_and_preserves_open_handle(self):
        self.assertEqual(self.request(19, b'/mnt'), (1, 128, 0, 38))
        self.assertEqual(self.request(19, b'/mnt', minor=6), (1, 128, 0, 2))
        for args in (dict(fd=1), dict(flags=1), dict(count=3)):
            self.assertEqual(self.request(19, b'/mnt', minor=6, **args), (1, 128, 0, 22))
        self.assertEqual(self.byte('open_count').value, 0)
        self.file(b'abc'); self.mount(); self.request(6, b'/mnt/HELLO')
        before = self.word('position').value
        self.assertEqual(self.request(19, b'/mnt', minor=6), (1, 128, 0, 16))
        self.assertEqual(self.word('position').value, before)
        self.assertEqual(self.read_all(), b'abc')

    def test_statfs_keeps_counted_non_nul_06_path_contract(self):
        self.mount(); self.bam(); self.sync()
        self.assertEqual(self.request(19, b'/mntX', count=4, minor=6), (1, 2, 8, 0))

    def test_statfs_corrupt_bam_and_io_errors_close_and_allow_retry(self):
        self.mount()
        for index, value in ((2, 66), (4, 22), (140, 18), (255, 18)):
            self.bam(True)[index] = value; self.sync()
            before = self.byte('close_count').value
            self.assertEqual(self.request(19, b'/mnt', minor=6), (1, 128, 0, 5))
            self.assertEqual(self.byte('close_count').value, before+1)
        self.bam()
        for field in ('command_error', 'talk_error', 'close_error', 'status_error'):
            self.byte(field).value = 2
            self.assertEqual(self.request(19, b'/mnt', minor=6), (1, 128, 0, 5))
            self.byte(field).value = 0
            self.assertEqual(self.request(19, b'/mnt', minor=6), (1, 2, 8, 0))

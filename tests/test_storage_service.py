# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StorageService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        library = Path(cls.temp.name) / 'storage.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', '-DUDEKS_STORAGE_HOST_TEST', '-I'+str(ROOT/'include'),
                        str(ROOT/'src/services/filesystem/iec_service.c'),
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
        self.tracks = (c.c_uint8 * 32).in_dll(self.lib, 'test_tracks')
        self.numbers = (c.c_uint8 * 32).in_dll(self.lib, 'test_numbers')
        self.sectors = (c.c_uint16 * 8192).in_dll(self.lib, 'test_sectors')
        self.disk = {(18, 1): bytearray(b'\0\xff'+bytes(254))}
        self.sync()

    def byte(self, name): return c.c_uint8.in_dll(self.lib, 'test_'+name)
    def word(self, name): return c.c_uint16.in_dll(self.lib, 'test_'+name)

    def sync(self):
        self.tracks[:] = bytes(32)
        for i, ((track, sector), data) in enumerate(self.disk.items()):
            self.tracks[i], self.numbers[i] = track, sector
            self.sectors[i*256:(i+1)*256] = data

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

    def request(self, op, payload=b'', fd=0, count=None, flags=0):
        self.r[:] = bytes(38)
        self.r[:6] = b'UTRQ\0\5'
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
        self.file(b'bye', b'LONG FILE NAME!', slot=1, first=1)
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
        for name in (b'', b'A'*17, b'A/B', b'@A', b'A,W', b'A*', b'A?', b'A:B', b'A\0B', b'\xc1'):
            self.assertEqual(self.request(6, b'/mnt/'+name), (1, 128, 0, 22))
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
        self.mount(); self.request(6, b'/mnt', 1)
        self.byte('close_error').value = 2
        self.assertEqual(self.request(9, fd=4), (1, 128, 0, 5))
        self.byte('close_error').value = 0
        self.assertEqual(self.request(18, b'/mnt'), (1, 2, 0, 0))

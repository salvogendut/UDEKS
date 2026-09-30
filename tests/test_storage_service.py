# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_cbm_directory import virtual_drive_directory

ROOT = Path(__file__).resolve().parents[1]


class StorageService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        library = Path(cls.temp.name) / 'storage.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', '-DUDEKS_STORAGE_HOST_TEST', '-I'+str(ROOT/'include'),
                        str(ROOT/'src/services/filesystem/iec_service.c'),
                        str(ROOT/'src/services/filesystem/cbm_directory.c'),
                        str(ROOT/'tests/fixtures/storage_transport.c'),
                        '-o', str(library)], check=True)
        cls.lib = c.CDLL(str(library))
        cls.lib.udeks_storage_dispatch.restype = c.c_uint8

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.lib.udeks_storage_reset()
        self.r = (c.c_uint8 * 38).in_dll(self.lib, 'udeks_storage_request')
        for name in ('open_error', 'close_error', 'open_count', 'close_count',
                     'dos_error', 'status_bad', 'status_error', 'talk_error'):
            self.byte(name).value = 0
        self.stream([0x100])

    def byte(self, name):
        return c.c_uint8.in_dll(self.lib, 'test_'+name)

    def request(self, op, payload=b'', fd=0, count=None, flags=0):
        self.r[:] = bytes(38)
        self.r[:6] = b'UTRQ\0\5'
        self.r[6:14] = (1, op, 73, fd, len(payload) if count is None else count,
                         0, 0, flags)
        self.r[14:14+len(payload)] = payload
        handled = self.lib.udeks_storage_dispatch()
        return handled, self.r[6], self.r[11], self.r[12]

    def mount(self):
        self.assertEqual(self.request(17, b'\x08/mnt'), (1, 2, 0, 0))

    def stream(self, data):
        values = (c.c_uint16 * 512).in_dll(self.lib, 'test_stream')
        values[:len(data)] = data
        c.c_uint16.in_dll(self.lib, 'test_length').value = len(data)

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
        self.mount()
        self.stream(virtual_drive_directory())
        self.assertEqual(self.request(6, b'/mnt', 1), (1, 2, 4, 0))
        self.assertEqual(self.request(18, b'/mnt'), (1, 128, 0, 16))
        self.assertEqual(self.request(6, b'/mnt', 1), (1, 128, 0, 24))
        self.assertEqual(self.request(7, fd=4, count=17), (1, 128, 0, 22))
        self.assertEqual(c.c_uint16.in_dll(self.lib, 'test_position').value, 0)
        self.assertEqual(self.request(7, fd=4, count=24), (1, 2, 7, 0))
        self.assertEqual(bytes(self.r[16:21]), b'HELLO')
        self.assertEqual(self.request(7, fd=4, count=24), (1, 2, 17, 0))
        # This virtual-drive fixture ends with the footer, marked EOI here.
        end = c.c_uint16.in_dll(self.lib, 'test_length').value
        (c.c_uint16 * 512).in_dll(self.lib, 'test_stream')[end-1] |= 0x100
        self.assertEqual(self.request(7, fd=4, count=24), (1, 2, 0, 0))
        self.assertEqual(self.request(7, fd=4, count=24), (1, 2, 0, 0))
        self.assertEqual(self.request(9, fd=4), (1, 2, 0, 0))
        self.assertEqual(self.request(9, fd=4), (1, 128, 0, 9))
        self.assertEqual(self.request(18, b'/mnt'), (1, 2, 0, 0))

    def test_io_failure_releases_channel_and_can_reopen(self):
        self.mount()
        self.stream([0x200])
        self.request(6, b'/mnt', 1)
        self.assertEqual(self.request(7, fd=4, count=24), (1, 128, 0, 5))
        self.assertEqual(self.byte('close_count').value, 2)
        self.request(9, fd=4)
        self.assertEqual(self.request(6, b'/mnt', 1), (1, 2, 4, 0))

    def test_stat_and_read_contract(self):
        self.assertEqual(self.request(6, b'/mnt', 1), (1, 128, 0, 2))
        self.mount()
        self.assertEqual(self.request(8, b'/mnt'), (1, 2, 3, 0))
        self.assertEqual(bytes(self.r[14:17]), b'\4\0\0')
        self.request(6, b'/mnt', 1)
        self.assertEqual(self.request(1, fd=4, count=24), (1, 128, 0, 21))
        self.assertEqual(self.request(1, fd=7, count=24), (1, 128, 0, 9))

    def test_file_reads_include_eoi_byte_and_repeatable_eof(self):
        self.mount()
        self.stream([ord('a'), 0, 0x1ff])
        self.assertEqual(self.request(6, b'/mnt/HELLO'), (1, 2, 4, 0))
        self.assertEqual(self.request(1, fd=4, count=25), (1, 128, 0, 22))
        self.assertEqual(self.request(1, fd=4, count=0), (1, 2, 0, 0))
        self.assertEqual(self.request(1, fd=4, count=2), (1, 2, 2, 0))
        self.assertEqual(bytes(self.r[14:16]), b'a\0')
        self.assertEqual(self.request(1, fd=4, count=24), (1, 2, 1, 0))
        self.assertEqual(self.r[14], 255)
        for _ in range(2): self.assertEqual(self.request(1, fd=4, count=24), (1, 2, 0, 0))
        self.assertEqual(self.request(7, fd=4, count=24), (1, 128, 0, 20))
        self.assertEqual(self.request(18, b'/mnt'), (1, 128, 0, 16))
        self.assertEqual(self.request(9, fd=4), (1, 2, 0, 0))
        self.assertEqual(self.request(18, b'/mnt'), (1, 2, 0, 0))

    def test_missing_file_and_status_errors_leave_slot_available(self):
        self.mount()
        for field, value, errno in (('dos_error', 62, 2), ('dos_error', 74, 5),
                                    ('status_bad', 1, 5), ('status_error', 2, 5),
                                    ('talk_error', 2, 5)):
            self.byte(field).value = value
            self.assertEqual(self.request(6, b'/mnt/NOFILE'), (1, 128, 0, errno))
            self.byte(field).value = 0
        self.assertEqual(self.request(6, b'/mnt/HELLO'), (1, 2, 4, 0))

    def test_bad_filenames_cannot_inject_dos_commands_or_wildcards(self):
        self.mount()
        before = self.byte('open_count').value
        for name in (b'', b'A'*17, b'A/B', b'@A', b'A,W', b'A*', b'A?', b'A:B', b'A\0B'):
            self.assertEqual(self.request(6, b'/mnt/'+name), (1, 128, 0, 22))
        self.assertEqual(self.byte('open_count').value, before)

    def test_partial_read_defers_io_error_but_never_claims_eof(self):
        self.mount()
        self.stream([65, 0x200])
        self.request(6, b'/mnt/HELLO')
        self.assertEqual(self.request(1, fd=4, count=24), (1, 2, 1, 0))
        self.assertEqual(self.r[14], 65)
        for _ in range(2): self.assertEqual(self.request(1, fd=4, count=24), (1, 128, 0, 5))
        self.assertEqual(self.request(9, fd=4), (1, 2, 0, 0))
        self.assertEqual(self.request(18, b'/mnt'), (1, 2, 0, 0))

    def test_eoi_on_first_byte_is_preserved_when_transport_reports_it(self):
        self.mount()
        self.stream([0x100])
        self.assertEqual(self.request(6, b'/mnt/ONE'), (1, 2, 4, 0))
        self.assertEqual(self.request(1, fd=4, count=24), (1, 2, 1, 0))
        self.assertEqual(self.r[14], 0)
        self.assertEqual(self.request(1, fd=4, count=24), (1, 2, 0, 0))
        self.assertEqual(self.request(9, fd=4), (1, 2, 0, 0))

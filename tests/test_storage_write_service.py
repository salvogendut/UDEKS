# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the actual service with a writer seam, without enabling boot writes.

Inherited cases re-run the read-only compatibility suite with writes compiled.
The separate cbm_write/empty suites exercise the real backend and DOS transport.
"""
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_storage_service as baseline

ROOT = baseline.ROOT
OK = (1, 2, 0, 0)
OPEN = (1, 2, 4, 0)


def error(code): return (1, 128, 0, code)


class StorageWriteService(baseline.StorageService):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        library = Path(cls.temp.name) / 'storage-write.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', '-DUDEKS_STORAGE_HOST_TEST', '-DUDEKS_STORAGE_WRITES',
                        '-I'+str(ROOT/'include'),
                        str(ROOT/'src/services/filesystem/iec_service.c'),
                        str(ROOT/'src/services/filesystem/fs_namespace.c'),
                        str(ROOT/'src/services/filesystem/cbm_file.c'),
                        str(ROOT/'tests/fixtures/storage_transport.c'),
                        str(ROOT/'tests/fixtures/storage_writer.c'), '-o', str(library)], check=True)
        cls.lib = c.CDLL(str(library))
        cls.lib.udeks_storage_dispatch.restype = c.c_uint8
        cls.lib.udeks_storage_cleanup.argtypes = [c.c_uint16]
        cls.lib.udeks_storage_cleanup.restype = c.c_uint8

    def setUp(self):
        super().setUp()
        self.lib.test_writer_reset()

    def mount14(self, unit=8, path=b'/mnt', flags=1):
        return self.request(17, bytes((unit,))+path, flags=flags, minor=14)

    def create(self, path=b'/mnt/new'):
        return self.request(6, path, fd=3, minor=14)

    def write(self, data=b'hello', **kwargs):
        return self.request(2, data, fd=4, minor=14, **kwargs)

    def close(self): return self.request(9, fd=4, minor=14)

    def test_legacy_mounts_and_recovery_are_read_only(self):
        self.mount()
        before = self.byte('open_count').value
        self.assertEqual(self.create(), error(30))
        self.assertEqual(self.create(b'/new'), error(30))
        self.assertEqual(self.byte('open_count').value, before)
        self.assertEqual(self.word('create_calls').value, 0)
        self.assertEqual(self.request(6, b'/mnt/new', fd=3, minor=13), error(22))
        self.assertEqual(self.mount14(flags=3), OK)
        self.assertEqual(self.create(), OPEN)

    def test_mount_flags_are_versioned_and_remount_needs_same_device(self):
        for minor in (5, 8, 13):
            self.assertEqual(self.request(17, b'\x08/mnt', flags=1, minor=minor), error(22))
        for flags in (4, 8, 255): self.assertEqual(self.mount14(flags=flags), error(22))
        self.assertEqual(self.mount14(flags=3), error(19))
        self.assertEqual(self.byte('open_count').value, 0)
        self.assertEqual(self.mount14(flags=0), OK)
        self.assertEqual(self.mount14(unit=9, flags=3), error(22))
        self.assertEqual(self.create(), error(30))
        self.assertEqual(self.mount14(flags=3), OK)
        self.assertEqual(self.create(), OPEN)

    def test_failed_rw_mount_does_not_publish_permissions(self):
        self.byte('open_error').value = 3
        self.assertEqual(self.mount14(), error(19))
        self.byte('open_error').value = 0
        self.mount()  # successful legacy read-only mount
        self.assertEqual(self.create(), error(30))

    def test_root_can_remount_after_boot_without_cwd_or_source_change(self):
        self.assertEqual(self.mount14(path=b'/', flags=0), OK)
        boot = c.c_uint8.in_dll(self.lib, 'udeks_storage_boot_source')
        cwd = c.c_uint8.in_dll(self.lib, 'udeks_storage_cwd')
        boot.value = 1; cwd.value = 2
        before = self.byte('open_count').value
        self.assertEqual(self.mount14(path=b'/', flags=3), OK)
        self.assertEqual((boot.value, cwd.value), (1, 2))
        self.assertEqual(self.byte('open_count').value, before)
        self.assertEqual(self.request(18, b'/', minor=14), error(16))
        self.assertEqual(self.mount14(unit=9, path=b'/', flags=3), error(22))
        self.assertEqual(self.create(b'/data'), OPEN)
        self.assertEqual(self.close(), OK)
        self.assertEqual(self.mount14(path=b'/', flags=2), OK)
        self.assertEqual(self.create(b'/data'), error(30))

    def test_no_writable_alias_in_either_mount_order(self):
        for first, second in ((b'/', b'/mnt'), (b'/mnt', b'/')):
            for flags in (0, 1):
                self.lib.udeks_storage_reset()
                self.assertEqual(self.mount14(path=first, flags=flags), OK)
                self.assertEqual(self.mount14(path=second), error(16))
                if flags:
                    self.assertEqual(self.mount14(path=second, flags=0), error(16))
                else:
                    self.assertEqual(self.mount14(path=second, flags=0), OK)
                    self.assertEqual(self.mount14(path=first, flags=3), error(16))
                    self.assertEqual(self.mount14(path=second, flags=3), error(16))

    def test_unmount_clears_rw_permission(self):
        self.assertEqual(self.mount14(), OK)
        self.assertEqual(self.request(18, b'/mnt', flags=1, minor=14), error(22))
        self.assertEqual(self.request(18, b'/mnt', minor=14), OK)
        self.mount()
        self.assertEqual(self.create(), error(30))

    def test_independent_drive_permissions_and_relative_create(self):
        self.assertEqual(self.mount14(path=b'/', flags=0), OK)
        self.assertEqual(self.mount14(unit=9), OK)
        self.assertEqual(self.create(b'/system-data'), error(30))
        self.assertEqual(self.request(21, b'/mnt', minor=14), OK)
        self.assertEqual(self.create(b'data'), OPEN)
        self.assertEqual(self.byte('create_unit').value, 9)
        self.assertEqual(self.close(), OK)
        self.assertEqual(self.mount14(path=b'/', flags=3), OK)
        self.assertEqual(self.create(b'/system-data'), OPEN)
        self.assertEqual(self.byte('create_unit').value, 8)

    def test_statfs_reports_effective_permissions(self):
        self.disk[18, 0] = bytearray(b'\x12\x01\x41\0'+bytes(252))
        self.sync()
        self.assertEqual(self.mount14(flags=0), OK)
        for flags, expected in ((2, 1), (3, 0), (2, 1)):
            self.assertEqual(self.mount14(flags=flags), OK)
            self.assertEqual(self.request(19, b'/mnt', minor=14), (1, 2, 8, 0))
            self.assertEqual(self.r[21], expected)

    def test_binary_create_write_close_and_maximum_name(self):
        self.assertEqual(self.mount14(), OK)
        self.assertEqual(self.create(b'/mnt/abcdefghijklmnop'), OPEN)
        self.assertEqual(self.byte('create_unit').value, 8)
        self.assertEqual(self.byte('create_length').value, 16)
        name = (c.c_uint8*16).in_dll(self.lib, 'test_create_name')
        self.assertEqual(bytes(name), b'ABCDEFGHIJKLMNOP')
        data = b'\0\r\xff'+bytes(range(21))
        self.assertEqual(self.write(data), (1, 2, 24, 0))
        sent = (c.c_uint8*24).in_dll(self.lib, 'test_write_data')
        self.assertEqual(bytes(sent), data)
        self.assertEqual(self.close(), OK)
        self.assertEqual(self.word('writer_close_calls').value, 1)
        self.assertEqual(self.close(), error(9))
        self.assertEqual(self.create(), OPEN)

    def test_plain_data_only_and_validation_before_io(self):
        self.assertEqual(self.mount14(path=b'/'), OK)
        before = self.byte('open_count').value
        for path, errno in ((b'/new.BIN', 2), (b'/new.SH', 2), (b'/new.ETC', 2),
                            (b'/bin/new', 22), (b'/etc/new', 22),
                            (b'/bin', 21), (b'/etc', 21), (b'/', 21),
                            (b'/ bad', 22), (b'/bad ', 22), (b'/a,w', 22),
                            (b'/a*', 22), (b'/@a', 22), (b'/a\0b', 22)):
            self.assertEqual(self.create(path), error(errno), path)
        self.assertEqual(self.byte('open_count').value, before)
        self.assertEqual(self.word('create_calls').value, 0)

    def test_data_mount_can_create_suffix_names_without_alias_translation(self):
        self.assertEqual(self.mount14(), OK)
        self.assertEqual(self.create(b'/mnt/report.etc'), OPEN)
        name = (c.c_uint8*16).in_dll(self.lib, 'test_create_name')
        self.assertEqual(bytes(name), b'REPORT.ETC'+b'\xa0'*6)

    def test_preflight_rejects_existing_folded_splat_locked_and_wrong_types(self):
        self.assertEqual(self.mount14(), OK)
        for name in (b'NEW', b'new', b'\xce\xc5\xd7'):
            for kind in (0x81, 1, 0xc1, 0x82, 0x84):
                self.file(b'untouched', name)
                self.disk[18, 1][2] = kind
                self.sync()
                before = list(self.sectors)
                self.assertEqual(self.create(), error(17), (name, kind))
                self.assertEqual(list(self.sectors), before)
        self.assertEqual(self.word('create_calls').value, 0)

    def test_complete_collision_scan_and_directory_failure_precede_create(self):
        self.file(b'a', b'NEW')
        self.file(b'b', b'new', slot=1, first=1)
        self.assertEqual(self.mount14(), OK)
        self.assertEqual(self.create(), error(17))
        self.assertEqual(self.word('create_calls').value, 0)
        self.disk[18, 1][0:2] = bytes((18, 2))  # missing next directory sector
        self.sync()
        self.assertEqual(self.create(b'/mnt/absent'), error(5))
        self.assertEqual(self.word('create_calls').value, 0)
        self.assertEqual(self.close(), error(9))

    def test_create_failure_leaves_handle_available(self):
        self.assertEqual(self.mount14(), OK)
        for errno in (5, 17, 19, 28, 30):
            self.byte('create_error').value = errno
            self.assertEqual(self.create(), error(errno))
            self.assertEqual(self.close(), error(9))
        self.byte('create_error').value = 0
        self.assertEqual(self.create(), OPEN)

    def test_owner_and_generation_are_not_request_supplied(self):
        self.assertEqual(self.mount14(), OK)
        self.word('caller').value = 0
        before = self.byte('open_count').value
        self.assertEqual(self.create(), error(3))
        self.assertEqual(self.byte('open_count').value, before)
        self.word('caller').value = 0x301
        self.assertEqual(self.create(), OPEN)
        for caller in (0, 0x401, 0x302):
            self.word('caller').value = caller
            self.assertEqual(self.write(), error(9))
            self.assertEqual(self.close(), error(9))
            self.assertEqual(self.lib.udeks_storage_cleanup(caller), 0)
        self.assertEqual(self.word('writer_close_calls').value, 0)
        self.word('caller').value = 0x301
        self.assertEqual(self.write(b'ok'), (1, 2, 2, 0))
        self.assertEqual(self.close(), OK)

    def test_read_handles_also_require_owner_and_cleanup_closes_them(self):
        self.file(b'content'); self.mount()
        self.word('caller').value = 7
        self.assertEqual(self.request(6, b'/mnt/HELLO'), OPEN)
        self.word('caller').value = 8
        self.assertEqual(self.request(1, fd=4, count=24), error(9))
        self.assertEqual(self.close(), error(9))
        before = self.byte('close_count').value
        self.assertEqual(self.lib.udeks_storage_cleanup(7), 0)
        self.assertEqual(self.byte('close_count').value, before+1)
        self.assertEqual(self.request(6, b'/mnt/HELLO'), OPEN)
        self.assertEqual(self.read_all(), b'content')

    def test_directory_cleanup_and_eof_read_cleanup_do_not_close_twice(self):
        self.file(b'content'); self.mount()
        for path, fd in ((b'/mnt', 1), (b'/mnt/HELLO', 0)):
            self.assertEqual(self.request(6, path, fd), OPEN)
            if not fd: self.assertEqual(self.read_all(), b'content')
            before = self.byte('close_count').value
            self.assertEqual(self.lib.udeks_storage_cleanup(1), 0)
            self.assertEqual(self.byte('close_count').value, before)
            self.assertEqual(self.close(), error(9))

    def test_read_cleanup_failure_still_releases_owner(self):
        self.file(b'content'); self.mount()
        self.assertEqual(self.request(6, b'/mnt/HELLO'), OPEN)
        self.byte('close_error').value = 2
        self.assertEqual(self.lib.udeks_storage_cleanup(1), 5)
        self.assertEqual(self.lib.udeks_storage_cleanup(1), 0)
        self.byte('close_error').value = 0
        self.word('caller').value = 2
        self.assertEqual(self.request(6, b'/mnt/HELLO'), OPEN)

    def test_cleanup_is_idempotent_releases_on_error_and_preserves_request(self):
        self.assertEqual(self.mount14(), OK)
        self.word('caller').value = 51
        self.assertEqual(self.create(), OPEN)
        before = bytes(self.r)
        self.byte('writer_close_error').value = 28
        self.assertEqual(self.lib.udeks_storage_cleanup(51), 28)
        self.assertEqual(bytes(self.r), before)
        self.assertEqual(self.lib.udeks_storage_cleanup(51), 0)
        self.assertEqual(self.word('writer_close_calls').value, 1)
        self.word('caller').value = 52
        self.assertEqual(self.create(b'/mnt/another'), OPEN)
        self.assertEqual(self.lib.udeks_storage_cleanup(51), 0)
        self.assertEqual(self.word('writer_close_calls').value, 1)
        self.assertEqual(self.write(b'x'), (1, 2, 1, 0))

    def test_handle_barrier_blocks_mount_remount_second_open_and_statfs(self):
        self.assertEqual(self.mount14(), OK)
        self.assertEqual(self.create(), OPEN)
        before = self.byte('open_count').value
        self.assertEqual(self.mount14(flags=2), error(16))
        self.assertEqual(self.mount14(unit=9, path=b'/'), error(16))
        self.assertEqual(self.request(18, b'/mnt', minor=14), error(16))
        self.assertEqual(self.request(19, b'/mnt', minor=14), error(16))
        self.assertEqual(self.create(b'/mnt/other'), error(24))
        self.assertEqual(self.request(6, b'/mnt', fd=1, minor=14), error(24))
        self.assertEqual(self.byte('open_count').value, before)
        self.assertEqual(self.close(), OK)
        self.assertEqual(self.mount14(flags=2), OK)

    def test_invalid_write_and_close_requests_do_not_consume_or_poison(self):
        self.assertEqual(self.mount14(), OK)
        self.assertEqual(self.create(), OPEN)
        self.assertEqual(self.write(b'', count=25), error(22))
        self.assertEqual(self.write(flags=1), error(22))
        self.assertEqual(self.request(2, b'x', fd=4, minor=13), error(9))
        self.assertEqual(self.request(9, b'x', fd=4, minor=14), error(22))
        self.assertEqual(self.request(9, fd=4, flags=1, minor=14), error(22))
        self.assertEqual(self.request(1, fd=4, count=24, minor=14), error(9))
        self.assertEqual(self.request(7, fd=4, count=24, minor=14), error(20))
        self.assertEqual(self.word('write_calls').value, 0)
        self.assertEqual(self.word('writer_close_calls').value, 0)
        self.assertEqual(self.write(), (1, 2, 5, 0))
        self.assertEqual(self.close(), OK)

    def test_readonly_or_directory_handle_cannot_be_written(self):
        self.file(b'keep'); self.assertEqual(self.mount14(), OK)
        for path, fd in ((b'/mnt/HELLO', 0), (b'/mnt', 1)):
            self.assertEqual(self.request(6, path, fd=fd, minor=14), OPEN)
            self.assertEqual(self.write(), error(9))
            self.assertEqual(self.word('write_calls').value, 0)
            self.assertEqual(self.close(), OK)

    def test_short_write_reports_prefix_once_then_sticky_error_and_close(self):
        self.assertEqual(self.mount14(), OK)
        for n in range(25):
            self.assertEqual(self.create(), OPEN)
            self.byte('write_prefix').value = n
            self.byte('write_error').value = 28
            self.assertEqual(self.write(bytes(range(24))), (1, 2, n, 0) if n else error(28))
            calls = self.word('write_calls').value
            self.byte('write_error').value = 0
            for data in (b'', b'retry'):
                self.assertEqual(self.write(data), error(28))
            self.assertEqual(self.word('write_calls').value, calls)
            self.byte('writer_close_error').value = 5
            self.assertEqual(self.close(), error(28))
            self.assertEqual(self.close(), error(9))

    def test_empty_close_and_finalization_failure_are_checked(self):
        self.assertEqual(self.mount14(), OK)
        for errno in (0, 5, 28, 30):
            self.assertEqual(self.create(), OPEN)
            self.assertEqual(self.write(b''), OK)
            self.byte('writer_close_error').value = errno
            self.assertEqual(self.close(), error(errno) if errno else OK)
            self.assertEqual(self.close(), error(9))
        self.assertEqual(self.word('writer_close_calls').value, 4)

    def test_console_and_other_dispatch_fallbacks_are_untouched(self):
        for op, fd in ((2, 1), (2, 2), (10, 0), (24, 0), (255, 0)):
            self.request(op, b'abc', fd=fd, minor=14)
            before = bytes(self.r)
            self.assertEqual(self.lib.udeks_storage_dispatch(), 0)
            self.assertEqual(bytes(self.r), before)
        for fd in (0, 3, 5, 255):
            self.assertEqual(self.request(2, b'abc', fd=fd, minor=14), error(9))


if __name__ == '__main__': unittest.main()

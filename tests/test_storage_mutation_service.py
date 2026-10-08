# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual candidate service + namespace/sector reader; captured mutation seam.

No mutation entry is installed in the shipping kernel yet. Inherited cases
repeat read/create compatibility with candidate handlers compiled in.
"""
import ctypes as c
from pathlib import Path
import subprocess
import tempfile
import unittest
import test_storage_write_service as baseline

ROOT = baseline.ROOT
OK, OPEN, error = baseline.OK, baseline.OPEN, baseline.error
RENAME, COPY, UNLINK = 25, 26, 27


class StorageMutationService(baseline.StorageWriteService):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        library = Path(cls.temp.name) / 'storage-mutation.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                        '-DUDEKS_STORAGE_HOST_TEST', '-DUDEKS_STORAGE_WRITES',
                        '-DUDEKS_STORAGE_MUTATIONS', '-DUDEKS_FS_CLIENT_TEST', '-D__fastcall__=',
                        '-I'+str(ROOT/'include'), '-I'+str(ROOT/'user/include'),
                        *[str(ROOT/p) for p in (
                            'src/services/filesystem/iec_service.c',
                            'src/services/filesystem/fs_namespace.c',
                            'src/services/filesystem/cbm_file.c',
                            'tests/fixtures/storage_transport.c',
                            'tests/fixtures/storage_writer.c',
                            'tests/fixtures/storage_mutator.c',
                            'tests/fixtures/file_mutation_client.c',
                            'user/lib/filesystem.c', 'user/lib/file_mutation.c')], '-o', str(library)], check=True)
        cls.lib = c.CDLL(str(library))
        cls.lib.udeks_storage_dispatch.restype = c.c_uint8
        cls.lib.udeks_storage_cleanup.argtypes = [c.c_uint16]
        cls.lib.udeks_storage_cleanup.restype = c.c_uint8
        for name in ('rename','copy','unlink'):
            fn = getattr(cls.lib, 'udeks_'+name)
            fn.restype = c.c_uint8
            fn.argtypes = [c.c_char_p] if name == 'unlink' else [c.c_char_p, c.c_char_p]

    def setUp(self):
        super().setUp()
        self.word('mutate_calls').value = 0
        self.byte('mutate_error').value = 0
        self.byte('sdk_calls').value = 0
        self.byte('sdk_close_error').value = 0

    def source(self, data=b'\0\xffbinary', name=b'HELLO', kind=0x81, root=False):
        self.file(data, name)
        self.disk[18, 1][2] = kind
        self.sync()
        self.assertEqual(self.mount14(path=b'/' if root else b'/mnt'), OK)
        return self.request(6, (b'/' if root else b'/mnt/')+name, minor=18)

    def mutation(self, op=RENAME, destination=b'/mnt/target', **kwargs):
        return self.request(op, b'' if op == UNLINK else destination, fd=4, minor=18, **kwargs)

    def captured(self, name):
        return bytes((c.c_uint8*16).in_dll(self.lib, 'test_mutate_'+name))

    def no_mutation(self):
        self.assertEqual(self.word('mutate_calls').value, 0)
        self.assertEqual(self.word('create_calls').value, 0)

    def test_pending_operation_binds_owner_and_operation_and_never_resends(self):
        self.source()
        self.byte('mutate_error').value = 11
        self.assertEqual(self.mutation(COPY), (1,2,1,0))
        self.assertEqual(self.request(COPY,fd=4,minor=18,flags=1), (1,2,1,0))
        self.assertEqual(self.request(RENAME,fd=4,minor=18,flags=1),error(9))
        self.assertEqual(self.request(COPY,b'x',fd=4,minor=18,flags=1),error(22))
        self.word('caller').value = 2
        self.assertEqual(self.request(COPY,fd=4,minor=18,flags=1),error(9))
        self.word('caller').value = 1
        self.assertEqual(self.request(1,fd=4,minor=18,count=1),error(16))
        self.byte('mutate_error').value = 0
        self.assertEqual(self.request(COPY,fd=4,minor=18,flags=1), OK)
        self.assertEqual(self.word('mutate_calls').value, 1)
        self.assertEqual(self.close(),error(9))

    def test_pending_cleanup_releases_bus_before_owner_reuse(self):
        self.source()
        self.byte('mutate_error').value = 11
        self.assertEqual(self.mutation(RENAME), (1,2,1,0))
        before=self.word('mutate_aborts').value
        self.assertEqual(self.lib.udeks_storage_cleanup(2),0)
        self.assertEqual(self.word('mutate_aborts').value,before)
        self.assertEqual(self.lib.udeks_storage_cleanup(1),0)
        self.assertEqual(self.word('mutate_aborts').value,before+1)
        self.assertEqual(self.request(RENAME,fd=4,minor=18,flags=1),error(9))

    def test_pending_failure_and_explicit_close_release_ownership(self):
        self.source()
        self.byte('mutate_error').value=11
        self.assertEqual(self.mutation(UNLINK),(1,2,1,0))
        self.byte('mutate_error').value=5
        self.assertEqual(self.request(UNLINK,fd=4,minor=18,flags=1),error(5))
        self.assertEqual(self.close(),error(9))
        self.assertEqual(self.request(6,b'/mnt/HELLO',minor=18),OPEN)
        self.byte('mutate_error').value=11
        self.assertEqual(self.mutation(UNLINK),(1,2,1,0))
        self.assertEqual(self.close(),OK)
        self.assertEqual(self.word('mutate_calls').value,2)

    def test_mutation_version_wire_and_owner_checks_preserve_handle(self):
        self.assertEqual(self.source(), OPEN)
        before = self.byte('open_count').value
        for op in (RENAME, COPY, UNLINK):
            self.assertEqual(self.request(op, fd=4, minor=17), error(38))
            for fd in (0, 3, 5, 255):
                self.assertEqual(self.request(op, b'' if op == UNLINK else b'target', fd=fd, minor=18), error(9))
            self.assertEqual(self.mutation(op, flags=2), error(22))
            for caller in (0, 0x101, 2):
                self.word('caller').value = caller
                self.assertEqual(self.mutation(op), error(9))
            self.word('caller').value = 1
        for op, count in ((RENAME, 0), (COPY, 24), (UNLINK, 1)):
            self.assertEqual(self.request(op, fd=4, minor=18, count=count), error(22))
        self.r[:] = b'UTRQ\0\x12'+bytes((1, RENAME, 0, 4, 6, 0, 0, 0))+b'targetX'+bytes(17)
        self.assertEqual(self.lib.udeks_storage_dispatch(), 1)
        self.assertEqual(self.r[12], 22)  # missing terminator
        self.assertEqual(self.byte('open_count').value, before)
        self.no_mutation()
        self.assertEqual(self.read_all(), b'\0\xffbinary')
        self.assertEqual(self.close(), OK)

    def test_exact_mutations_consume_descriptor_once(self):
        for op, physical in ((RENAME, 1), (COPY, 2), (UNLINK, 3)):
            self.setUp()
            self.assertEqual(self.source(), OPEN)
            self.assertEqual(self.mutation(op), OK)
            self.assertEqual(self.word('mutate_calls').value, 1)
            self.assertEqual(self.byte('mutate_unit').value, 8)
            self.assertEqual(self.byte('mutate_op').value, physical)
            self.assertEqual(self.captured('source'), b'HELLO'+b'\xa0'*11)
            self.assertEqual(self.byte('mutate_has_destination').value, op != UNLINK)
            if op != UNLINK:
                self.assertEqual(self.captured('destination'), b'TARGET'+b'\xa0'*10)
            self.assertEqual(self.close(), error(9))
            self.assertEqual(self.mutation(op), error(9))
            self.assertEqual(self.word('mutate_calls').value, 1)

    def test_ro_locked_unsupported_and_directory_handles_never_mutate(self):
        for kind, expected in ((0xc1, 16), (0xc2, 16), (0x83, 22)):
            self.setUp()
            self.assertEqual(self.source(kind=kind), OPEN)
            self.assertEqual(self.mutation(), error(expected))
            self.no_mutation()
            self.assertEqual(self.close(), OK)
        self.setUp()
        self.file(b'keep'); self.mount()
        self.assertEqual(self.request(6, b'/mnt/hello'), OPEN)
        self.assertEqual(self.mutation(UNLINK), error(30))
        self.assertEqual(self.close(), OK)
        self.assertEqual(self.request(6, b'/mnt', fd=1), OPEN)
        self.assertEqual(self.mutation(), error(21))
        self.assertEqual(self.close(), OK)
        self.assertEqual(self.mount14(flags=3), OK)
        self.assertEqual(self.create(), OPEN)
        self.assertEqual(self.mutation(), error(9))
        self.assertEqual(self.close(), OK)
        self.assertEqual(self.word('mutate_calls').value, 0)

    def test_missing_splat_rel_and_duplicate_sources_fail_open(self):
        for kind, expected in ((1, 22), (0x84, 22)):
            self.setUp()
            self.assertEqual(self.source(kind=kind), error(expected))
            self.assertEqual(self.mutation(UNLINK), error(9))
            self.no_mutation()
        self.setUp()
        self.file(b'a', b'HELLO'); self.file(b'b', b'hello', slot=1, first=1)
        self.mount14()
        self.assertEqual(self.request(6, b'/mnt/hello'), error(17))
        self.assertEqual(self.request(6, b'/mnt/absent'), error(2))
        self.assertEqual(self.mutation(UNLINK), error(9))
        self.no_mutation()

    def test_destination_preflight_retains_handle_and_never_sends(self):
        self.assertEqual(self.source(), OPEN)
        for path, expected in ((b'/mnt',21), (b'/mnt/a*',22), (b'/mnt/@x',22),
                               (b'/mnt/a,w',22), (b'/mnt/a:b',22), (b'/mnt/a=b',22),
                               (b'/mnt/ x',22), (b'/mnt/x ',22), (b'/mnt/a\0b',22),
                               (b'/missing',19)):
            self.assertEqual(self.mutation(destination=path), error(expected), path)
        self.no_mutation()
        self.assertEqual(self.read_all(), b'\0\xffbinary')

    def test_cross_device_and_other_request_scratch_do_not_redirect_mutation(self):
        self.file(b'data')
        self.assertEqual(self.mount14(path=b'/'), OK)
        self.assertEqual(self.mount14(unit=9), OK)
        self.assertEqual(self.request(6, b'/hello', minor=18), OPEN)
        self.assertEqual(self.mutation(destination=b'/mnt/target'), error(18))
        self.assertEqual(self.request(6, b'/mnt/wrong', minor=18), error(24))
        self.assertEqual(self.request(8, b'/mnt', minor=18), (1,2,3,0))
        self.assertEqual(self.request(21, b'/mnt', minor=18), OK)
        self.assertEqual(self.mutation(destination=b'/target'), OK)
        self.assertEqual(self.byte('mutate_unit').value, 8)
        self.assertEqual(self.captured('source'), b'HELLO'+b'\xa0'*11)

    def test_collision_same_path_folded_and_ambiguous_all_close_without_mutation(self):
        self.file(b'keep', b'TARGET', slot=1, first=1)
        self.assertEqual(self.source(), OPEN)
        for destination in (b'/mnt/hello',b'/mnt/HELLO',b'/mnt/target'):
            self.assertEqual(self.mutation(destination=destination), error(17))
            self.assertEqual(self.close(), error(9))
            self.assertEqual(self.request(6,b'/mnt/hello',minor=18), OPEN)
        self.file(b'keep2', b'target', slot=2, first=2)
        self.assertEqual(self.mutation(destination=b'/mnt/target'), error(17))
        self.no_mutation()

    def test_source_spaces_do_not_reach_dos_even_for_empty_copy(self):
        for name in (b' HELLO', b'HELLO '):
            self.setUp()
            self.assertEqual(self.source(data=b'',name=name), OPEN)
            self.assertEqual(self.mutation(COPY), error(22))
            self.no_mutation()
            self.assertEqual(self.close(), OK)

    def test_suffix_mapping_and_type_preservation(self):
        for source, logical, destination, physical in (
            (b'APP.BIN', b'/bin/app', b'/bin/new', b'NEW.BIN'),
            (b'APP.SH', b'/bin/app', b'/bin/new', b'NEW.SH'),
            (b'RC.ETC', b'/etc/rc', b'/etc/new', b'NEW.ETC'),
            (b'APP.BIN', b'/bin/app', b'/ordinary', b'ORDINARY'),
            (b'DATA', b'/data', b'/bin/new', b'NEW.BIN')):
            self.setUp()
            self.file(b'\0\x0e\xff',source)
            self.disk[18,1][2] = 0x82; self.sync()
            self.mount14(path=b'/')
            self.assertEqual(self.request(6,logical,minor=18), OPEN)
            self.assertEqual(self.mutation(COPY,destination), OK)
            self.assertEqual(self.captured('source'), source.ljust(16,b'\xa0'))
            self.assertEqual(self.captured('destination'), physical.ljust(16,b'\xa0'))
            self.assertEqual(self.word('create_calls').value, 0)

    def test_bin_collision_includes_both_suffixes(self):
        self.file(b'a',b'A.BIN'); self.file(b'b',b'TARGET.SH',slot=1,first=1)
        self.mount14(path=b'/')
        self.assertEqual(self.request(6,b'/bin/a',minor=18), OPEN)
        self.assertEqual(self.mutation(destination=b'/bin/target'),error(17))
        self.no_mutation()

    def test_empty_is_verified_from_start_and_uses_checked_writer_with_source_type(self):
        for data, kind in ((b'',0x81),(b'',0x82),(b'x',0x81),(b'\0\xff',0x82)):
            self.setUp()
            self.assertEqual(self.source(data=data,kind=kind), OPEN)
            self.assertEqual(self.read_all(), data)  # previously reached EOF!
            self.assertEqual(self.mutation(COPY),OK)
            self.assertEqual(self.word('mutate_calls').value, bool(data))
            self.assertEqual(self.word('create_calls').value, not data)
            if not data:
                self.assertEqual(self.byte('create_type').value,kind & 3)
                self.assertEqual(self.word('writer_close_calls').value,1)
                self.assertEqual(self.word('write_calls').value,0)

    def test_copy_probe_close_directory_and_full_disk_failures_precede_mutation(self):
        for failure in ('close', 'read', 'directory', 'full'):
            self.setUp(); self.assertEqual(self.source(), OPEN)
            if failure == 'close': self.byte('close_error').value=2
            elif failure == 'read': self.disk[1,0][1]=0; self.sync()
            elif failure == 'directory': self.disk[18,1][:2]=b'\x12\x02'; self.sync()
            else:
                for track in range(1,36): self.disk[18,0][4*track]=0
                self.sync()
            self.assertEqual(self.mutation(COPY),error(28 if failure=='full' else 5))
            self.no_mutation()
            self.assertEqual(self.close(),error(9))

    def test_backend_and_empty_finalization_errors_never_retry_or_keep_owner(self):
        for empty in (False,True):
            for errno in (5,17,19,28,30):
                self.setUp(); self.assertEqual(self.source(data=b'' if empty else b'keep'),OPEN)
                self.byte('writer_close_error' if empty else 'mutate_error').value=errno
                self.assertEqual(self.mutation(COPY),error(errno))
                self.assertEqual(self.close(),error(9))
                self.assertEqual(self.lib.udeks_storage_cleanup(1),0)
                self.assertEqual(self.word('writer_close_calls' if empty else 'mutate_calls').value,1)

    def test_sdk_opens_owns_and_cleans_up_without_retry(self):
        for name, op in (('rename',RENAME),('copy',COPY),('unlink',UNLINK)):
            for errno in (0,5,28,30):
                self.setUp(); self.file(b'keep'); self.mount14()
                self.byte('mutate_error').value=errno
                args=[b'/mnt/hello'] if name=='unlink' else [b'/mnt/hello',b'/mnt/target']
                self.assertEqual(getattr(self.lib,'udeks_'+name)(*args),255 if errno else 0)
                self.assertEqual(c.c_uint8.in_dll(self.lib,'udeks_errno').value,errno)
                self.assertEqual(self.word('mutate_calls').value,1)
                trace=(c.c_uint8*8).in_dll(self.lib,'test_sdk_operations')
                self.assertEqual(bytes(trace[:self.byte('sdk_calls').value]),bytes((6,op,9)))
                self.assertEqual(self.close(),error(9))

    def test_sdk_closes_preflight_rejections_preserving_primary_error(self):
        self.file(b'keep'); self.mount()
        self.byte('sdk_close_error').value=2
        self.assertEqual(self.lib.udeks_copy(b'/mnt/hello',b'/mnt/target'),255)
        self.assertEqual(c.c_uint8.in_dll(self.lib,'udeks_errno').value,30)
        self.assertEqual(self.close(),error(9))
        self.no_mutation()

    def test_sdk_invalid_destination_is_rejected_before_open(self):
        self.file(b'keep'); self.mount14()
        for destination in (None,b'',b'X'*24):
            self.assertEqual(self.lib.udeks_copy(b'/mnt/hello',destination),255)
        self.assertEqual(self.byte('sdk_calls').value,0)
        self.no_mutation()

    def test_sdk_failed_open_never_mutates_or_closes_an_unowned_fd(self):
        self.file(b'keep'); self.mount14()
        self.assertEqual(self.lib.udeks_unlink(b'/mnt/missing'),255)
        self.assertEqual(c.c_uint8.in_dll(self.lib,'udeks_errno').value,2)
        self.assertEqual(self.byte('sdk_calls').value,1)
        self.no_mutation()


if __name__ == '__main__': unittest.main()

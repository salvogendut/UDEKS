# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the actual C namespace policy, independently of IEC I/O and cc65 layout."""
import ctypes as c
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROOT_DIR, BIN, ETC, MNT = range(4)
NONE, RAW, BINARY, SCRIPT, CONFIG = range(5)
ENOENT, EEXIST, ENODEV, ENOTDIR, EINVAL = 2, 17, 19, 20, 22


class PathResult(c.Structure):
    _fields_ = [('directory', c.c_uint8), ('length', c.c_uint8),
                ('name', c.c_uint8 * 17)]


class Volumes(c.Structure):
    _fields_ = [('root', c.c_uint8), ('data', c.c_uint8)]


def raw(name):
    assert len(name) <= 16
    return name.ljust(16, b'\xa0')


def filled():
    return PathResult.from_buffer_copy(b'\x5a' * c.sizeof(PathResult))


class FilesystemNamespace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        library = Path(cls.temp.name) / 'namespace.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                        '-shared', '-fPIC', '-I'+str(ROOT/'include'),
                        str(ROOT/'src/services/filesystem/fs_namespace.c'),
                        '-o', str(library)], check=True)
        cls.lib = c.CDLL(str(library))
        cls.lib.udeks_fs_resolve.argtypes = [c.c_char_p, c.c_uint8, c.c_uint8,
                                           c.POINTER(PathResult)]
        cls.lib.udeks_fs_device.argtypes = [c.POINTER(Volumes), c.c_uint8,
                                          c.POINTER(c.c_uint8)]
        cls.lib.udeks_fs_classify.argtypes = [c.c_char_p, c.c_uint8,
                                            c.POINTER(PathResult), c.POINTER(c.c_uint8)]
        cls.lib.udeks_fs_physical.argtypes = [c.POINTER(PathResult), c.c_uint8, c.c_void_p]
        cls.lib.udeks_fs_consider.argtypes = [c.POINTER(PathResult), c.c_char_p,
                                            c.POINTER(c.c_uint8)]
        for name in ('resolve', 'device', 'classify', 'physical', 'consider'):
            getattr(cls.lib, 'udeks_fs_'+name).restype = c.c_uint8

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def resolve(self, text, cwd=ROOT_DIR, error=0):
        result = filled()
        before = bytes(result)
        self.assertEqual(self.lib.udeks_fs_resolve(text, len(text), cwd, c.byref(result)), error)
        if error:
            self.assertEqual(bytes(result), before, text)
        else:
            self.assertEqual(bytes(result.name)[result.length:], bytes(17-result.length))
        return result

    def classify(self, name, data=0, error=0):
        result, kind = filled(), c.c_uint8(0x5a)
        self.assertEqual(self.lib.udeks_fs_classify(raw(name), data,
                         c.byref(result), c.byref(kind)), error, name)
        if error:
            self.assertEqual(bytes(result), b'\x5a'*19)
            self.assertEqual(kind.value, 0x5a)
        return result, kind.value

    def physical(self, result, kind, error=0):
        # Guard both sides of the output, even for successful maximum lengths.
        buffer = c.create_string_buffer(b'\x5a'*18, 18)
        self.assertEqual(self.lib.udeks_fs_physical(c.byref(result), kind,
                         c.byref(buffer, 1)), error)
        self.assertEqual(buffer.raw[0], 0x5a)
        self.assertEqual(buffer.raw[-1], 0x5a)
        if error: self.assertEqual(buffer.raw, b'\x5a'*18)
        return buffer.raw[1:-1]

    def assert_path(self, result, directory, name=b''):
        self.assertEqual(result.directory, directory)
        self.assertEqual(result.length, len(name))
        self.assertEqual(bytes(result.name), name.ljust(17, b'\0'))

    def test_root_virtual_directories_and_case(self):
        for text, directory in ((b'/', ROOT_DIR), (b'/bin', BIN),
                                (b'/ETC', ETC), (b'/MnT', MNT)):
            self.assert_path(self.resolve(text), directory)

    def test_absolute_path_does_not_depend_on_cwd(self):
        for cwd in range(4):
            self.assert_path(self.resolve(b'/etc/RC', cwd), ETC, b'rc')
            self.assert_path(self.resolve(b'/mnt/BIN', cwd), MNT, b'bin')

    def test_relative_names_and_dot(self):
        for cwd in range(4):
            self.assert_path(self.resolve(b'.', cwd), cwd)
            self.assert_path(self.resolve(b'./HeLLo', cwd), cwd, b'hello')
        self.assert_path(self.resolve(b'etc/rc'), ETC, b'rc')
        self.assert_path(self.resolve(b'mnt', BIN), BIN, b'mnt')

    def test_parent_at_root_and_across_mount_boundary(self):
        for cwd in range(4):
            self.assert_path(self.resolve(b'..', cwd), ROOT_DIR)
            self.assert_path(self.resolve(b'../../..', cwd), ROOT_DIR)
            self.assert_path(self.resolve(b'../bin/ush', cwd), BIN, b'ush')
        self.assert_path(self.resolve(b'/mnt/../etc/./rc'), ETC, b'rc')

    def test_repeated_slashes_and_directory_trailing_slash(self):
        for text, directory in ((b'////', ROOT_DIR), (b'//bin///', BIN),
                                (b'/mnt//../etc/.//', ETC)):
            self.assert_path(self.resolve(text), directory)
        self.assert_path(self.resolve(b'///mnt//FILE'), MNT, b'file')

    def test_does_not_erase_file_traversal(self):
        for text in (b'/bin/ush/', b'/bin/ush/.', b'/bin/ush/..',
                     b'nope/../bin', b'/mnt/file/../other', b'/other/file'):
            self.resolve(text, error=ENOTDIR)

    def test_prefix_is_not_mountpoint(self):
        self.assert_path(self.resolve(b'/mnt-other'), ROOT_DIR, b'mnt-other')
        self.resolve(b'/mnt-other/file', error=ENOTDIR)
        self.assert_path(self.resolve(b'/binary'), ROOT_DIR, b'binary')

    def test_bounded_input_not_nul_terminated(self):
        result = filled()
        self.assertEqual(self.lib.udeks_fs_resolve(b'/binIGNORED', 4, 0, c.byref(result)), 0)
        self.assert_path(result, BIN)
        self.assert_path(self.resolve(b'///mnt/' + b'a'*16), MNT, b'a'*16)  # 23 bytes
        self.resolve(b'////mnt/' + b'a'*16, error=EINVAL)

    def test_rejects_unsupported_characters_without_output_mutation(self):
        for text in (b'', b'/mnt/A'*5, b'/mnt/'+b'a'*17, b'\0', b'/etc/r\0c',
                     b'/mnt/@a', b'/mnt/a:b', b'/mnt/a,w', b'/bin/a*',
                     b'/bin/a?', b'/mnt/\xc1', b'/mnt/\xff', b'/mnt/a\n',
                     b'/mnt/a\\b'):
            self.resolve(text, error=EINVAL)
        self.resolve(b'/', cwd=4, error=EINVAL)

    def test_stem_limits_account_for_suffix_bytes(self):
        for directory, limit in ((b'/bin/', 13), (b'/etc/', 12), (b'/mnt/', 16)):
            self.resolve(directory + b'a'*limit)
            self.resolve(directory + b'a'*(limit+1), error=EINVAL)
        p = self.resolve(b'/bin/' + b'a'*13)
        self.physical(p, BINARY, error=EINVAL)
        self.assertEqual(self.physical(p, SCRIPT), b'A'*13+b'.SH')
        self.assertEqual(self.physical(self.resolve(b'/bin/'+b'a'*12), BINARY), b'A'*12+b'.BIN')

    def test_system_suffix_mapping_and_inverse(self):
        for filename, directory, name, kind in (
                (b'USH.BIN', BIN, b'ush', BINARY),
                (b'STARTUP.SH', BIN, b'startup', SCRIPT),
                (b'RC.ETC', ETC, b'rc', CONFIG),
                (b'README', ROOT_DIR, b'readme', RAW),
                (b'NOTES.TXT', ROOT_DIR, b'notes.txt', RAW)):
            result, actual_kind = self.classify(filename)
            self.assert_path(result, directory, name)
            self.assertEqual(actual_kind, kind)
            self.assertEqual(self.physical(result, kind), raw(filename))

    def test_usr_and_rc_are_not_classification_suffixes(self):
        for filename in (b'DATA.USR', b'OLD.RC', b'RC'):
            result, kind = self.classify(filename)
            self.assert_path(result, ROOT_DIR, filename.lower())
            self.assertEqual(kind, RAW)

    def test_only_final_suffix_classifies(self):
        for filename, directory, name, kind in (
                (b'FOO.BIN.BAK', ROOT_DIR, b'foo.bin.bak', RAW),
                (b'FOO.ETC.SH', BIN, b'foo.etc', SCRIPT),
                (b'.HELLO.BIN', BIN, b'.hello', BINARY)):
            result, actual = self.classify(filename)
            self.assert_path(result, directory, name)
            self.assertEqual(actual, kind)

    def test_data_mount_keeps_suffixes_and_flat_names(self):
        for filename in (b'FOO.BIN', b'RC.ETC', b'FOO.SH', b'ETC', b'MNT',
                         b'BIN', b'MY FILE.TXT', b'1234567890123456'):
            result, kind = self.classify(filename, data=1)
            self.assert_path(result, MNT, filename.lower())
            self.assertEqual(kind, RAW)
            self.assertEqual(self.physical(result, kind), raw(filename))

    def test_both_petscii_alphabets_and_ascii_case_fold(self):
        for name in (b'Clock.bin', bytes(x+128 if 65 <= x <= 90 else x for x in b'CLOCK.BIN')):
            result, kind = self.classify(name)
            self.assert_path(result, BIN, b'clock')
            self.assertEqual(kind, BINARY)

    def test_empty_stem_dot_names_and_invalid_padding_rejected(self):
        for name in (b'', b'.', b'..', b'.BIN', b'.SH', b'.ETC', b'..BIN',
                     b'...ETC', b'A\xa0B', b'A\0', b'A/B', b'A*', b'A,W', b'\xff'):
            self.classify(name, error=EINVAL)
        # .BIN has a non-empty ordinary name on unclassified data media.
        self.assertEqual(self.classify(b'.BIN', data=1)[1], RAW)

    def test_virtual_directories_cannot_be_shadowed(self):
        for name in (b'BIN', b'Etc', b'mnt'):
            self.classify(name, error=EEXIST)
        self.assert_path(self.classify(b'BIN.BIN')[0], BIN, b'bin')

    def test_device_eight_root_and_independent_device_nine_data(self):
        volumes = Volumes(8, 0)
        unit = c.c_uint8(0x5a)
        for directory in (ROOT_DIR, BIN, ETC):
            self.assertEqual(self.lib.udeks_fs_device(c.byref(volumes), directory, c.byref(unit)), 0)
            self.assertEqual(unit.value, 8)
        unit.value = 0x5a
        self.assertEqual(self.lib.udeks_fs_device(c.byref(volumes), MNT, c.byref(unit)), ENODEV)
        self.assertEqual(unit.value, 0x5a)
        volumes.data = 9
        for directory, expected in ((ROOT_DIR, 8), (BIN, 8), (ETC, 8), (MNT, 9)):
            self.assertEqual(self.lib.udeks_fs_device(c.byref(volumes), directory, c.byref(unit)), 0)
            self.assertEqual(unit.value, expected)
        volumes.data = 0
        self.assertEqual(self.lib.udeks_fs_device(c.byref(volumes), BIN, c.byref(unit)), 0)
        self.assertEqual(unit.value, 8)

    def test_missing_root_never_routes_system_commands_to_data(self):
        volumes, unit = Volumes(0, 9), c.c_uint8(0x5a)
        for directory in (ROOT_DIR, BIN, ETC):
            self.assertEqual(self.lib.udeks_fs_device(c.byref(volumes), directory, c.byref(unit)), ENODEV)
            self.assertEqual(unit.value, 0x5a)

    def test_route_is_not_hardcoded_to_device_eight(self):
        volumes, unit = Volumes(10, 11), c.c_uint8()
        for directory, expected in ((BIN, 10), (MNT, 11)):
            self.assertEqual(self.lib.udeks_fs_device(c.byref(volumes), directory, c.byref(unit)), 0)
            self.assertEqual(unit.value, expected)
        for bad in (1, 7, 12, 255):
            volumes.root, unit.value = bad, 0x5a
            self.assertEqual(self.lib.udeks_fs_device(c.byref(volumes), BIN, c.byref(unit)), EINVAL)
            self.assertEqual(unit.value, 0x5a)

    def test_invalid_physical_translation_is_atomic(self):
        for text, kind in ((b'/bin/ush', RAW), (b'/etc/rc', BINARY),
                           (b'/mnt/file', CONFIG), (b'/etc', CONFIG),
                           (b'/bin/ush', NONE), (b'/bin/ush', 255)):
            self.physical(self.resolve(text), kind, error=EINVAL)
        result = self.resolve(b'/bin/ush')
        result.name[1] = ord('*')
        self.physical(result, BINARY, error=EINVAL)

    def test_suffix_mapped_files_have_no_raw_root_alias(self):
        for text in (b'/ush.bin', b'/startup.sh', b'/rc.etc'):
            self.physical(self.resolve(text), RAW, error=ENOENT)
        self.assertEqual(self.physical(self.resolve(b'/mnt/ush.bin'), RAW), raw(b'USH.BIN'))

    def test_invalid_query_does_not_poison_streaming_selection(self):
        query, selected = self.resolve(b'/bin/foo'), c.c_uint8(NONE)
        query.name[1] = ord('*')
        self.consider(query, b'FOO.BIN', selected, EINVAL)
        query = self.resolve(b'/bin/foo')
        query.name[3] = ord('x')
        self.consider(query, b'FOO.BIN', selected, EINVAL)

    def consider(self, query, name, selected, expected):
        before = selected.value
        self.assertEqual(self.lib.udeks_fs_consider(c.byref(query), raw(name),
                                                   c.byref(selected)), expected)
        if expected: self.assertEqual(selected.value, before)

    def test_bin_sh_collision_rejected_in_either_directory_order(self):
        query = self.resolve(b'/bin/foo')
        for first, second, kind in ((b'FOO.BIN', b'FOO.SH', BINARY),
                                    (b'FOO.SH', b'FOO.BIN', SCRIPT)):
            selected = c.c_uint8(NONE)
            self.consider(query, first, selected, 0)
            self.assertEqual(selected.value, kind)
            self.consider(query, b'BAR.BIN', selected, ENOENT)
            self.consider(query, second, selected, EEXIST)

    def test_same_kind_and_folded_duplicates_rejected(self):
        query = self.resolve(b'/bin/foo')
        for second in (b'FOO.BIN', b'foo.bin', b'Foo.Bin', b'\xc6\xcf\xcf.BIN'):
            selected = c.c_uint8(NONE)
            self.consider(query, b'FOO.BIN', selected, 0)
            self.consider(query, second, selected, EEXIST)

    def test_unrelated_names_and_directories_do_not_match(self):
        selected = c.c_uint8(NONE)
        query = self.resolve(b'/bin/foo')
        for name in (b'FOO', b'FOO.ETC', b'FOO.USR', b'FOO.RC', b'FOOBAR.BIN'):
            self.consider(query, name, selected, ENOENT)
        self.consider(query, b'FOO.SH', selected, 0)
        self.assertEqual(selected.value, SCRIPT)

    def test_data_view_does_not_merge_bin_and_sh(self):
        query, selected = self.resolve(b'/mnt/foo.bin'), c.c_uint8(NONE)
        self.consider(query, b'FOO.SH', selected, ENOENT)
        self.consider(query, b'FOO.BIN', selected, 0)
        self.assertEqual(selected.value, RAW)
        self.consider(query, b'foo.bin', selected, EEXIST)

    def test_random_valid_names_round_trip_without_truncation(self):
        rng = random.Random(26)
        for _ in range(500):
            suffix = rng.choice((b'.BIN', b'.SH', b'.ETC', b'.TXT'))
            stem = bytes(rng.choice(b'abcdef0123_-') for _ in range(rng.randint(1, 16-len(suffix))))
            physical = (stem+suffix).upper()
            for data in (0, 1):
                result, kind = self.classify(physical, data)
                self.assertEqual(self.physical(result, kind), raw(physical))
                prefix = (b'/', b'/bin/', b'/etc/', b'/mnt/')[result.directory]
                logical = self.resolve(prefix + bytes(result.name[:result.length]))
                self.assertEqual(bytes(logical), bytes(result))

# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_d71 import build_image, validate_command, d64_compatibility_image
from build_udex import build_executable
from managed_app_fixture import dos_file


class DiskCommands(unittest.TestCase):
    def test_pack_and_reject_invalid_commands(self):
        exe = build_executable(b'\x60', cpu=1, load_address=0x200, entry_address=0x200)
        validate_command(exe)
        image = build_image(b'CBM\0\x1c\0\xd4'+bytes(25), b'', b'', b'', commands=(('COWSAY', exe), ('DATE', exe)))
        for view in (image, d64_compatibility_image(image)):
            _, offsets = dos_file(view, 'COWSAY.BIN')
            self.assertEqual(bytes(view[p] for p in offsets), exe)
        for bad in (exe[:-1], exe+b'x', bytes(17)):
            with self.assertRaises(ValueError): validate_command(bad)
        for index, value in ((4, 1), (5, 2), (6, 2), (7, 2), (9, 0x12), (13, 10), (14, 1)):
            bad = bytearray(exe); bad[index] = value
            with self.subTest(index=index), self.assertRaises(ValueError): validate_command(bad)

    def test_bootfs_contains_only_mount_helpers_and_recovery_shell(self):
        rule = (ROOT/'Makefile').read_text().split('$(USER_BOOTFS):', 1)[1].split('\n\n', 1)[0]
        for name in ('cowsay', 'date', 'ls', 'cat', 'xclock', 'xwave'):
            self.assertNotIn('--entry '+name+'=', rule)
        self.assertIn('--entry mount=$(USER_RECOVERY_MOUNT_UDEX)', rule)
        self.assertIn('--entry umount=$(USER_RECOVERY_MOUNT_UDEX)', rule)
        self.assertIn('--entry ush=$(USER_RECOVERY_USH_UDEX)', rule)

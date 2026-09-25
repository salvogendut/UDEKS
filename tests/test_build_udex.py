# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_udex import (
    ABI_MAJOR,
    ABI_MINOR,
    FLAG_MANAGED_APP,
    FLAG_PERSISTENT_POLL,
    HEADER_SIZE,
    MAGIC,
    build_executable,
)


class BuildUdexTests(unittest.TestCase):
    def test_public_header_matches_packer_constants(self):
        header = (ROOT / "include/udeks/executable.h").read_text()
        self.assertIn("UDEKS_EXECUTABLE_MAGIC0          'U'", header)
        self.assertIn("UDEKS_EXECUTABLE_MAGIC1          'D'", header)
        self.assertIn("UDEKS_EXECUTABLE_MAGIC2          'E'", header)
        self.assertIn("UDEKS_EXECUTABLE_MAGIC3          'X'", header)
        self.assertEqual(MAGIC, b"UDEX")
        self.assertIn(
            f"UDEKS_EXECUTABLE_ABI_MAJOR       {ABI_MAJOR}u", header
        )
        self.assertIn(
            f"UDEKS_EXECUTABLE_ABI_MINOR       {ABI_MINOR}u", header
        )
        self.assertIn(
            f"UDEKS_EXECUTABLE_HEADER_SIZE     {HEADER_SIZE}u", header
        )

    def test_wraps_fixed_address_8502_image(self):
        image = b"\x20\x00\x03\x60"
        executable = build_executable(
            image,
            cpu=1,
            load_address=0x0200,
            entry_address=0x0200,
            bss_size=12,
        )
        self.assertEqual(executable[:4], b"UDEX")
        self.assertEqual(executable[4:8], bytes((0, 1, 1, 0)))
        self.assertEqual(executable[8:10], b"\x00\x02")
        self.assertEqual(executable[10:12], len(image).to_bytes(2, "little"))
        self.assertEqual(executable[12:14], b"\x0c\x00")
        self.assertEqual(executable[14:16], b"\x00\x02")
        self.assertEqual(executable[HEADER_SIZE:], image)

    def test_accepts_z80_image(self):
        executable = build_executable(
            b"\xc9", cpu=2, load_address=0x8000, entry_address=0x8000
        )
        self.assertEqual(executable[6], 2)

    def test_rejects_unknown_cpu(self):
        with self.assertRaisesRegex(ValueError, "CPU"):
            build_executable(
                b"x", cpu=3, load_address=0x0200, entry_address=0x0200
            )

    def test_accepts_persistent_poll_flag(self):
        executable = build_executable(
            b"x",
            cpu=1,
            load_address=0x9000,
            entry_address=0x9000,
            flags=FLAG_PERSISTENT_POLL,
        )
        self.assertEqual(executable[7], FLAG_PERSISTENT_POLL)

    def test_accepts_managed_application_flag(self):
        executable = build_executable(
            bytes(18),
            cpu=1,
            load_address=0x1200,
            entry_address=0x1200,
            flags=FLAG_MANAGED_APP,
        )
        self.assertEqual(executable[7], FLAG_MANAGED_APP)

    def test_rejects_combined_lifecycle_flags(self):
        with self.assertRaisesRegex(ValueError, "flags conflict"):
            build_executable(
                bytes(18),
                cpu=1,
                load_address=0x1200,
                entry_address=0x1200,
                flags=FLAG_PERSISTENT_POLL | FLAG_MANAGED_APP,
            )

    def test_rejects_unsupported_flags(self):
        with self.assertRaisesRegex(ValueError, "unsupported flags"):
            build_executable(
                b"x", cpu=1, load_address=0x0200,
                entry_address=0x0200, flags=0x80,
            )

    def test_rejects_entry_outside_image(self):
        with self.assertRaisesRegex(ValueError, "entry"):
            build_executable(
                b"x", cpu=1, load_address=0x0200, entry_address=0x0201
            )

    def test_rejects_address_space_overflow(self):
        with self.assertRaisesRegex(ValueError, "target memory"):
            build_executable(
                bytes(32),
                cpu=1,
                load_address=0xFFF0,
                entry_address=0xFFF0,
            )


if __name__ == "__main__":
    unittest.main()

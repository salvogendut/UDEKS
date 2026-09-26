# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from join_boot_crt0 import (  # noqa: E402
    CRT0_ADDRESS,
    CRT0_SIZE,
    KERNEL_ADDRESS,
    PROBE_ADDRESS,
    PROBE_SIZE,
    join,
)


class JoinBootCrt0Tests(unittest.TestCase):
    def test_join_places_probe_then_crt0_then_kernel(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            probe = bytes([0x11]) * PROBE_SIZE
            crt0 = bytes([0x22]) * CRT0_SIZE
            kernel = bytes([0x33]) * 16
            destination = root / "direct.bin"

            join(probe, crt0, kernel, destination)

            image = destination.read_bytes()
            self.assertEqual(
                len(image), KERNEL_ADDRESS - PROBE_ADDRESS + len(kernel)
            )
            self.assertEqual(image[:PROBE_SIZE], probe)
            gap = image[PROBE_SIZE : CRT0_ADDRESS - PROBE_ADDRESS]
            self.assertEqual(gap, bytes(len(gap)))
            crt0_offset = CRT0_ADDRESS - PROBE_ADDRESS
            self.assertEqual(image[crt0_offset : crt0_offset + CRT0_SIZE], crt0)
            self.assertEqual(image[KERNEL_ADDRESS - PROBE_ADDRESS :], kernel)

    def test_rejects_oversize_probe(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "256-byte"):
                join(
                    bytes(PROBE_SIZE + 1),
                    bytes(CRT0_SIZE),
                    b"\x33",
                    root / "direct.bin",
                )

    def test_rejects_oversize_crt0(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "256-byte"):
                join(
                    bytes(PROBE_SIZE),
                    bytes(CRT0_SIZE + 1),
                    b"\x33",
                    root / "direct.bin",
                )

    def test_rejects_empty_kernel(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "empty"):
                join(
                    bytes(PROBE_SIZE),
                    bytes(CRT0_SIZE),
                    b"",
                    root / "direct.bin",
                )


if __name__ == "__main__":
    unittest.main()

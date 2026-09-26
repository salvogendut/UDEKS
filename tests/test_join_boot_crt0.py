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
    join,
)


class JoinBootCrt0Tests(unittest.TestCase):
    def test_join_places_crt0_then_pads_to_the_kernel(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            crt0 = bytes([0x11]) * CRT0_SIZE
            kernel = bytes([0x22]) * 16
            destination = root / "direct.bin"

            join(crt0, kernel, destination)

            image = destination.read_bytes()
            self.assertEqual(
                len(image), KERNEL_ADDRESS - CRT0_ADDRESS + len(kernel)
            )
            self.assertEqual(image[:CRT0_SIZE], crt0)
            gap = image[CRT0_SIZE : KERNEL_ADDRESS - CRT0_ADDRESS]
            self.assertEqual(gap, bytes(len(gap)))
            self.assertEqual(
                image[KERNEL_ADDRESS - CRT0_ADDRESS :], kernel
            )

    def test_rejects_oversize_crt0(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "256-byte"):
                join(
                    bytes(CRT0_SIZE + 1),
                    b"\x22",
                    root / "direct.bin",
                )

    def test_rejects_empty_kernel(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "empty"):
                join(bytes(CRT0_SIZE), b"", root / "direct.bin")


if __name__ == "__main__":
    unittest.main()

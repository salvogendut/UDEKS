# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from bin_to_prg import convert  # noqa: E402


class BinToPrgTests(unittest.TestCase):
    def test_prepends_little_endian_load_address(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.bin"
            destination = root / "output.prg"
            source.write_bytes(b"\x11\x22\x33")

            convert(source, destination, 0x2000)

            self.assertEqual(destination.read_bytes(), b"\x00\x20\x11\x22\x33")

    def test_rejects_image_past_end_of_address_space(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.bin"
            source.write_bytes(b"\0" * 3)

            with self.assertRaisesRegex(ValueError, "beyond"):
                convert(source, root / "output.prg", 0xFFFE)


if __name__ == "__main__":
    unittest.main()

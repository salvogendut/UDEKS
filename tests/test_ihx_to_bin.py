# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ihx_to_bin import convert, read_ihx  # noqa: E402


class IhxToBinTests(unittest.TestCase):
    def test_converts_and_pads_requested_range(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.ihx"
            destination = root / "output.bin"
            source.write_text(":03200000010203D7\n:00000001FF\n")

            convert(source, destination, 0x2000, 0x2008)

            self.assertEqual(destination.read_bytes(), b"\x01\x02\x03" + b"\0" * 5)

    def test_rejects_bad_checksum(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "bad.ihx"
            source.write_text(":0120000001DF\n:00000001FF\n")

            with self.assertRaisesRegex(ValueError, "checksum"):
                read_ihx(source)


if __name__ == "__main__":
    unittest.main()

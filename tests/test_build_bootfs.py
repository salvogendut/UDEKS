# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_bootfs import ENTRY_SIZE, HEADER_SIZE, MAGIC, build_bootfs


class BuildBootfsTests(unittest.TestCase):
    def test_builds_sorted_directory_and_payloads(self):
        image = build_bootfs([("ush", b"shell"), ("cowsay", b"cow")])

        self.assertEqual(image[:4], MAGIC)
        self.assertEqual(image[4:8], bytes((0, 1, 2, ENTRY_SIZE)))
        self.assertEqual(int.from_bytes(image[8:10], "little"), HEADER_SIZE)
        self.assertEqual(image[HEADER_SIZE + 1], 6)
        self.assertEqual(image[HEADER_SIZE + 8 : HEADER_SIZE + 14], b"cowsay")
        second = HEADER_SIZE + ENTRY_SIZE
        self.assertEqual(image[second + 8 : second + 11], b"ush")
        first_offset = int.from_bytes(image[HEADER_SIZE + 2 : HEADER_SIZE + 4], "little")
        second_offset = int.from_bytes(image[second + 2 : second + 4], "little")
        self.assertEqual(image[first_offset:first_offset + 3], b"cow")
        self.assertEqual(image[second_offset:second_offset + 5], b"shell")

    def test_rejects_duplicate_names(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_bootfs([("ush", b"one"), ("ush", b"two")])

    def test_rejects_paths_in_leaf_names(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            build_bootfs([("/bin/ush", b"shell")])

    def test_rejects_oversize_image(self):
        with self.assertRaisesRegex(ValueError, "configured size"):
            build_bootfs([("large", bytes(128))], max_size=64)


if __name__ == "__main__":
    unittest.main()

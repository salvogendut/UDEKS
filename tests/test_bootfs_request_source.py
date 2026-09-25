# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BootfsRequestSourceTests(unittest.TestCase):
    def test_dot_resolves_through_the_root_session_directory(self):
        source = (
            ROOT / "src/services/filesystem/bootfs_request.s"
        ).read_text().lower()

        self.assertIn("cwd_kind                = $f2a6", source)
        self.assertIn("open_current:", source)
        self.assertIn("lda cwd_kind", source)
        self.assertIn("beq open_root", source)


if __name__ == "__main__":
    unittest.main()

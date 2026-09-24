# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StreamSourceTests(unittest.TestCase):
    def test_standard_descriptors_follow_unix_numbering(self):
        header = (ROOT / "include/udeks/stream.h").read_text(encoding="utf-8")
        self.assertIn("UDEKS_STDIN                     0u", header)
        self.assertIn("UDEKS_STDOUT                    1u", header)
        self.assertIn("UDEKS_STDERR                    2u", header)

    def test_initial_stream_backend_is_console_bound_not_vdc_bound(self):
        source = (ROOT / "src/services/terminal/stream.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("udeks_root_console_write(value)", source)
        self.assertNotIn("0xd600", source.lower())
        self.assertNotIn("0xd601", source.lower())


if __name__ == "__main__":
    unittest.main()

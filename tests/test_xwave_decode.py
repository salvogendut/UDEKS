# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from xwave_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(32)
    block[:4] = b"XWAV"
    block[4:8] = bytes((1, 3, 0, 7))
    block[8] = 2
    block[12:14] = (2).to_bytes(2, "little")
    block[16:18] = (1).to_bytes(2, "little")
    block[20:24] = bytes((144, 88, 168, 104))
    block[25] = 1
    return block


class XwaveDecodeTests(unittest.TestCase):
    def test_accepts_running_dual_engine_plot(self):
        result = parse_result(valid_record())
        self.assertEqual(result["state"], 3)
        self.assertEqual(result["z80_batches"], 2)
        self.assertEqual(result["fallback_batches"], 0)
        self.assertEqual(result["focused"], 1)

    def test_accepts_initialized_idle_application(self):
        block = valid_record()
        block[5] = 2
        block[8:26] = bytes(18)
        self.assertEqual(parse_result(block)["state"], 2)

    def test_rejects_running_application_without_a_render(self):
        block = valid_record()
        block[16:18] = b"\x00\x00"
        with self.assertRaisesRegex(ValueError, "not rendered"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from window_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(32)
    block[:4] = b"WMGR"
    block[4:6] = bytes((1, 2))
    block[6:9] = bytes((1, 1, 0))
    block[14:16] = bytes((4, 0x0F))
    block[16:18] = (1).to_bytes(2, "little")
    block[20:22] = (1).to_bytes(2, "little")
    return block


class WindowDecodeTests(unittest.TestCase):
    def test_accepts_idle_manager(self):
        result = parse_result(valid_record())
        self.assertEqual(result["active"], 1)
        self.assertEqual(result["repaints"], 1)

    def test_accepts_active_outline_drag(self):
        block = valid_record()
        block[8:13] = bytes((1, 124, 0, 61, 72))
        block[24:26] = (1).to_bytes(2, "little")
        result = parse_result(block)
        self.assertEqual(result["dragging"], 1)
        self.assertEqual(result["outline_x"], 124)

    def test_rejects_idle_drag_geometry(self):
        block = valid_record()
        block[9] = 1
        with self.assertRaisesRegex(ValueError, "idle"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

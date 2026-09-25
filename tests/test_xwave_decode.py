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
    block[4:8] = bytes((3, 3, 0, 7))
    block[8] = 2
    block[9:12] = bytes((21, 25, 2))
    block[12:14] = (21).to_bytes(2, "little")
    block[16:18] = (1).to_bytes(2, "little")
    block[18:20] = (525).to_bytes(2, "little")
    block[20:24] = bytes((144, 88, 168, 104))
    block[25] = 1
    return block


class XwaveDecodeTests(unittest.TestCase):
    def test_accepts_running_dual_engine_plot(self):
        result = parse_result(valid_record())
        self.assertEqual(result["state"], 3)
        self.assertEqual(result["z80_batches"], 21)
        self.assertEqual(result["fallback_batches"], 0)
        self.assertEqual(result["surface_rows"], 21)
        self.assertEqual(result["surface_columns"], 25)
        self.assertEqual(result["mesh_axes"], 2)
        self.assertEqual(result["samples"], 525)
        self.assertEqual(result["focused"], 1)

    def test_accepts_initialized_idle_application(self):
        block = valid_record()
        block[5] = 2
        block[8:26] = bytes(18)
        self.assertEqual(parse_result(block)["state"], 2)

    def test_accepts_legacy_sine_plot_record(self):
        block = valid_record()
        block[4] = 1
        block[9:12] = bytes(3)
        block[18:20] = bytes(2)
        self.assertEqual(parse_result(block)["format"], 1)

    def test_accepts_legacy_hidden_line_surface_record(self):
        block = valid_record()
        block[4] = 2
        block[11] = 1
        result = parse_result(block)
        self.assertEqual(result["hidden_lines"], 1)
        self.assertEqual(result["mesh_axes"], 0)

    def test_rejects_running_application_without_a_render(self):
        block = valid_record()
        block[16:18] = b"\x00\x00"
        with self.assertRaisesRegex(ValueError, "not rendered"):
            parse_result(block)

    def test_rejects_running_mesh_with_wrong_grid(self):
        block = valid_record()
        block[10] = 24
        with self.assertRaisesRegex(ValueError, "mesh geometry"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

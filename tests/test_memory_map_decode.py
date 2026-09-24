# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from memory_map_decode import EXPECTED_OBSERVATIONS, parse_result


def valid_block() -> bytearray:
    block = bytearray(128)
    block[:10] = b"MAPQ\x01\x02\x17\x17\x00\x00"
    block[16 : 16 + len(EXPECTED_OBSERVATIONS)] = EXPECTED_OBSERVATIONS
    return block


class MemoryMapDecodeTests(unittest.TestCase):
    def test_accepts_complete_probe(self):
        result = parse_result(valid_block())
        self.assertEqual(result["passed"], 23)
        self.assertEqual(result["observations"][16:18], [0x6B, 0xB6])

    def test_rejects_incomplete_probe(self):
        block = valid_block()
        block[5] = 1
        with self.assertRaisesRegex(ValueError, "not complete"):
            parse_result(block)

    def test_reports_probe_failure(self):
        block = valid_block()
        block[5] = 0x91
        block[10] = 0x6B
        block[11] = 0x5A
        with self.assertRaisesRegex(ValueError, "check 0x11"):
            parse_result(block)

    def test_rejects_wrong_observation(self):
        block = valid_block()
        block[32] = 0x5A
        with self.assertRaisesRegex(ValueError, "observation 16"):
            parse_result(block)

    def test_preserved_emulator_records_pass(self):
        result_root = ROOT / "bench/results/2026-09-24-memory-map-profiles/raw"
        for name in ("vice-3.10.bin", "1986-7556c23.bin"):
            with self.subTest(result=name):
                result = parse_result((result_root / name).read_bytes())
                self.assertEqual(result["passed"], 23)


if __name__ == "__main__":
    unittest.main()

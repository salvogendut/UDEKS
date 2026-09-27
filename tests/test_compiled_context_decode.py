# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from compiled_context_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(32)
    block[:7] = b"UCCS\x01\x01\x02"
    block[8] = 64
    block[10:12] = b"\x20\x20"
    block[12:16] = b"\x44\x14\x41\x47"
    block[16:18] = b"\x02\x03"
    block[18:22] = b"\xF0\x70\xF0\x71"
    return block


class CompiledContextDecodeTests(unittest.TestCase):
    def test_accepts_a_complete_cc65_context_run(self):
        result = parse_result(valid_record())
        self.assertEqual(result["switches"], 64)
        self.assertEqual(result["sum_a"], 0x1444)
        self.assertEqual(result["sum_b"], 0x4741)
        self.assertEqual(result["software_stack_a"], 0x70F0)
        self.assertEqual(result["software_stack_b"], 0x71F0)

    def test_rejects_magic_format_cpu_and_state(self):
        block = valid_record()
        block[0] = ord("X")
        with self.assertRaisesRegex(ValueError, "not UCCS"):
            parse_result(block)
        block = valid_record()
        block[4] = 2
        with self.assertRaisesRegex(ValueError, "format 2"):
            parse_result(block)
        block = valid_record()
        block[5] = 2
        with self.assertRaisesRegex(ValueError, "CPU identifier 2"):
            parse_result(block)
        block = valid_record()
        block[6] = 0x82
        block[7] = 7
        with self.assertRaisesRegex(ValueError, "failure 7"):
            parse_result(block)

    def test_rejects_context_corruption(self):
        for offset, pattern in (
            (8, "switch count"),
            (10, "task steps"),
            (12, "task sums"),
            (16, "not relocation"),
            (17, "completion mask"),
            (18, "software stacks"),
            (22, "unused result"),
        ):
            block = valid_record()
            block[offset] ^= 1
            with self.assertRaisesRegex(ValueError, pattern):
                parse_result(block)

    def test_preserved_emulator_records_pass(self):
        raw = ROOT / "bench/results/2026-09-27-context-switch-c/raw"
        for name in ("1986.bin", "vice-1mhz.bin", "vice-2mhz.bin"):
            result = parse_result((raw / name).read_bytes())
            self.assertEqual(result["switches"], 64)


if __name__ == "__main__":
    unittest.main()

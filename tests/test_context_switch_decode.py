# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from context_switch_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(32)
    block[0:4] = b"CXSW"
    block[4] = 1
    block[5] = 1
    block[6] = 2
    block[8] = 64
    block[9] = 128
    block[11] = 7
    block[12] = 128
    block[15] = 0x02
    block[16] = 2
    block[17] = 1
    block[18] = 64
    block[19] = 64
    return block


class ContextSwitchDecodeTests(unittest.TestCase):
    def test_accepts_a_complete_relocation_run(self):
        result = parse_result(valid_record())
        self.assertEqual(result["rounds"], 64)
        self.assertEqual(result["switches"], 128)
        self.assertEqual(result["interrupts"], 7)
        self.assertEqual(result["checks_ok"], 128)
        self.assertEqual(result["step_a"], 64)
        self.assertEqual(result["step_b"], 64)
        self.assertEqual(result["page_bytes_per_switch"], 0)

    def test_rejects_bad_magic_format_and_cpu(self):
        block = valid_record()
        block[0] = ord("X")
        with self.assertRaisesRegex(ValueError, "not CXSW"):
            parse_result(block)
        block = valid_record()
        block[4] = 2
        with self.assertRaisesRegex(ValueError, "format 2"):
            parse_result(block)
        block = valid_record()
        block[5] = 2
        with self.assertRaisesRegex(ValueError, "CPU identifier 2"):
            parse_result(block)

    def test_rejects_running_and_failed_states(self):
        block = valid_record()
        block[6] = 1
        with self.assertRaisesRegex(ValueError, "not complete"):
            parse_result(block)
        block = valid_record()
        block[6] = 0x85
        block[7] = 5
        with self.assertRaisesRegex(ValueError, "code 5"):
            parse_result(block)

    def test_rejects_inconsistent_counts(self):
        block = valid_record()
        block[9] = 127
        with self.assertRaisesRegex(ValueError, "does not match"):
            parse_result(block)
        block = valid_record()
        block[11] = 0
        with self.assertRaisesRegex(ValueError, "interrupts"):
            parse_result(block)
        block = valid_record()
        block[13] = 1
        with self.assertRaisesRegex(ValueError, "check failures"):
            parse_result(block)
        block = valid_record()
        block[14] = 1
        with self.assertRaisesRegex(ValueError, "canary failures"):
            parse_result(block)
        block = valid_record()
        block[18] = 63
        with self.assertRaisesRegex(ValueError, "step counts"):
            parse_result(block)

    def test_rejects_a_non_relocation_result(self):
        block = valid_record()
        block[15] = 0
        with self.assertRaisesRegex(ValueError, "did not report success"):
            parse_result(block)
        block = valid_record()
        block[16] = 1
        with self.assertRaisesRegex(ValueError, "not relocation"):
            parse_result(block)

    def test_rejects_page_transfers_in_the_relocation_result(self):
        block = valid_record()
        block[20] = 1
        with self.assertRaisesRegex(ValueError, "1 page bytes"):
            parse_result(block)

    def test_rejects_a_short_record(self):
        with self.assertRaisesRegex(ValueError, "expected 32"):
            parse_result(valid_record()[:16])


if __name__ == "__main__":
    unittest.main()

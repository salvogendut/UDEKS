# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from task_state_decode import parse_result


def valid_record() -> bytearray:
    return bytearray(
        b"UTSK\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    )


class TaskStateDecodeTests(unittest.TestCase):
    def test_accepts_an_empty_ready_table(self):
        result = parse_result(valid_record())
        self.assertEqual(result["abi_major"], 0)
        self.assertEqual(result["abi_minor"], 1)
        self.assertEqual(result["current"], 0)
        self.assertEqual(result["defined"], 0)
        self.assertEqual(result["switches"], 0)

    def test_reports_little_endian_switch_count_and_counters(self):
        block = valid_record()
        block[7] = 1
        block[8] = 2
        block[9] = 3
        block[10] = 4
        block[11] = 5
        block[12:14] = b"\x34\x12"
        block[14] = 2
        result = parse_result(block)
        self.assertEqual(result["current"], 1)
        self.assertEqual(result["runnable"], 2)
        self.assertEqual(result["defined"], 3)
        self.assertEqual(result["rejected"], 4)
        self.assertEqual(result["canary"], 5)
        self.assertEqual(result["switches"], 0x1234)
        self.assertEqual(result["last_event"], 2)

    def test_rejects_bad_magic_and_abi(self):
        block = valid_record()
        block[0] = ord("X")
        with self.assertRaisesRegex(ValueError, "not UTSK"):
            parse_result(block)
        block = valid_record()
        block[5] = 2
        with self.assertRaisesRegex(ValueError, "ABI 0.2"):
            parse_result(block)

    def test_rejects_uninitialized_and_failed_tables(self):
        block = valid_record()
        block[6] = 0
        with self.assertRaisesRegex(ValueError, "uninitialized"):
            parse_result(block)
        block[6] = 0x83
        with self.assertRaisesRegex(ValueError, "code 3"):
            parse_result(block)

    def test_rejects_inconsistent_counts(self):
        block = valid_record()
        block[8] = 3
        block[9] = 2
        with self.assertRaisesRegex(ValueError, "runnable count"):
            parse_result(block)
        block = valid_record()
        block[9] = 9
        with self.assertRaisesRegex(ValueError, "capacity"):
            parse_result(block)
        block = valid_record()
        block[7] = 9
        with self.assertRaisesRegex(ValueError, "outside the table"):
            parse_result(block)
        block = valid_record()
        block[7] = 1
        with self.assertRaisesRegex(ValueError, "no runnable"):
            parse_result(block)

    def test_rejects_a_nonzero_reserved_byte(self):
        block = valid_record()
        block[15] = 1
        with self.assertRaisesRegex(ValueError, "reserved"):
            parse_result(block)

    def test_rejects_a_short_record(self):
        with self.assertRaisesRegex(ValueError, "expected 16"):
            parse_result(valid_record()[:8])


if __name__ == "__main__":
    unittest.main()

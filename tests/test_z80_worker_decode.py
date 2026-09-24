# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from z80_worker_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(32)
    block[:4] = b"ZWRK"
    block[4] = 1
    block[5] = 2
    block[8:10] = (2).to_bytes(2, "little")
    block[12:14] = (2).to_bytes(2, "little")
    block[16:18] = b"\x00\x01"
    block[18:21] = b"\x01\x01\x01"
    block[21] = 3
    return block


class Z80WorkerDecodeTests(unittest.TestCase):
    def test_accepts_ready_stock_worker(self):
        result = parse_result(valid_record())
        self.assertEqual(result["transactions"], 2)
        self.assertEqual(result["sequence"], 2)
        self.assertEqual(result["stock_timing"], 1)

    def test_rejects_ready_record_without_transaction(self):
        block = valid_record()
        block[12:14] = b"\x00\x00"
        with self.assertRaisesRegex(ValueError, "no transactions"):
            parse_result(block)

    def test_rejects_non_stock_timing_policy(self):
        block = valid_record()
        block[20] = 2
        with self.assertRaisesRegex(ValueError, "stock-timing"):
            parse_result(block)

    def test_rejects_incomplete_mailbox(self):
        block = valid_record()
        block[21] = 2
        with self.assertRaisesRegex(ValueError, "did not complete"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from handoff_decode import parse_result  # noqa: E402


def valid_result() -> bytearray:
    block = bytearray(64)
    block[:4] = b"HNDF"
    block[4] = 1
    block[5] = 2
    block[6] = 4
    block[7] = 8
    block[8:10] = (64).to_bytes(2, "little")
    block[10] = 1
    block[12] = 2
    for index, ticks in enumerate((640, 1280, 768, 1536), start=0):
        offset = 16 + index * 8
        block[offset] = index + 1
        block[offset + 2 : offset + 4] = (64).to_bytes(2, "little")
        block[offset + 4 : offset + 6] = ticks.to_bytes(2, "little")
        block[offset + 6 : offset + 8] = (64).to_bytes(2, "little")
    return block


class HandoffDecodeTests(unittest.TestCase):
    def test_parses_complete_valid_result(self):
        result = parse_result(valid_result())

        self.assertEqual(result["8502_mhz"], 2)
        self.assertIn("not-encoded", result["z80_timing_requirement"])
        self.assertEqual(result["records"][0]["ticks_per_round_trip"], 10.0)
        self.assertEqual(
            result["mailbox_overhead"]["z80_requester_ticks_per_transaction"],
            12.0,
        )

    def test_rejects_incomplete_result_with_error_name(self):
        block = valid_result()
        block[5] = 0x80
        block[11] = 2

        with self.assertRaisesRegex(ValueError, "mailbox"):
            parse_result(block)

    def test_rejects_wrong_peer_count(self):
        block = valid_result()
        block[16 + 6] = 63

        with self.assertRaisesRegex(ValueError, "peer count"):
            parse_result(block)

    def test_rejects_timer_overflow(self):
        block = valid_result()
        block[16 + 4 : 16 + 6] = b"\xff\xff"

        with self.assertRaisesRegex(ValueError, "invalid ticks"):
            parse_result(block)

    def test_rejects_unknown_speed(self):
        block = valid_result()
        block[12] = 4

        with self.assertRaisesRegex(ValueError, "speed"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

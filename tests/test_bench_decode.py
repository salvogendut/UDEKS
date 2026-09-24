# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from bench_decode import expected_checksums, extract_result, parse_result  # noqa: E402


def valid_result() -> bytearray:
    block = bytearray(128)
    block[:4] = b"BMRK"
    block[4] = 1
    block[5] = 1
    block[6] = 2
    block[7] = 6
    block[8] = 2
    block[9] = 8
    block[10] = 1
    iterations = (1, 128, 128, 128, 128, 64)
    for index, (case_id, checksum) in enumerate(expected_checksums().items()):
        offset = 16 + index * 8
        block[offset] = case_id
        block[offset + 2 : offset + 4] = iterations[index].to_bytes(2, "little")
        block[offset + 4 : offset + 6] = (100 + index).to_bytes(2, "little")
        block[offset + 6 : offset + 8] = checksum.to_bytes(2, "little")
    return block


class BenchDecodeTests(unittest.TestCase):
    def test_parses_complete_valid_result(self):
        result = parse_result(valid_result())

        self.assertEqual(result["cpu"], "8502")
        self.assertEqual(result["configuration"], 2)
        self.assertEqual(len(result["records"]), 6)
        self.assertEqual(result["records"][2]["name"], "copy")

    def test_rejects_wrong_workload_checksum(self):
        block = valid_result()
        block[16 + 6] ^= 1

        with self.assertRaisesRegex(ValueError, "checksum"):
            parse_result(block)

    def test_rejects_incomplete_result(self):
        block = valid_result()
        block[8] = 1

        with self.assertRaisesRegex(ValueError, "not complete"):
            parse_result(block)

    def test_rejects_timer_overflow(self):
        block = valid_result()
        block[16 + 4 : 16 + 6] = b"\xff\xff"

        with self.assertRaisesRegex(ValueError, "overflowed"):
            parse_result(block)

    def test_extracts_bank_zero_result_from_1986_snapshot(self):
        result = valid_result()
        private = bytearray(36 + 32 + 4 + 3 + 0x20000)
        private[:4] = b"1986"
        private[8:12] = (4).to_bytes(4, "little")
        private[12:16] = (3).to_bytes(4, "little")
        ram = 36 + 32 + 4 + 3
        private[ram + 0xF100 : ram + 0xF180] = result
        module = bytearray(22)
        module[:9] = b"1986STATE"
        module[18:22] = (22 + len(private)).to_bytes(4, "little")
        snapshot = bytearray(58) + module + private
        snapshot[:19] = b"VICE Snapshot File\x1a"

        self.assertEqual(extract_result(snapshot), result)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from offload_decode import (  # noqa: E402
    OP_NAMES,
    SIZES,
    expected_checksums,
    parse_result,
)


def valid_result() -> bytearray:
    block = bytearray(416)
    block[:4] = b"XOFS"
    block[4] = 1
    block[5] = 2
    block[6] = 3
    block[7] = 8
    block[8] = 16
    block[9] = 1
    block[10] = 2
    block[12] = 24
    block[13:16] = bytes((0xC0, 0xC8, 0x08))
    expected = expected_checksums()
    for op_id in OP_NAMES:
        for size_index, size in enumerate(SIZES):
            index = (op_id - 1) * len(SIZES) + size_index
            offset = 32 + index * 16
            block[offset] = op_id
            block[offset + 1] = 0x0F
            block[offset + 2 : offset + 4] = size.to_bytes(2, "little")
            local_8502 = size * 8
            to_z80 = local_8502 + 100
            local_z80 = size * 10
            to_8502 = local_z80 + 200 if size < 256 else local_z80 - 1
            for tick_index, ticks in enumerate(
                (local_8502, to_z80, local_z80, to_8502)
            ):
                tick_offset = offset + 4 + tick_index * 2
                block[tick_offset : tick_offset + 2] = ticks.to_bytes(2, "little")
            checksum = expected[op_id][size_index]
            block[offset + 12 : offset + 14] = checksum.to_bytes(2, "little")
            block[offset + 14 : offset + 16] = checksum.to_bytes(2, "little")
    return block


class OffloadDecodeTests(unittest.TestCase):
    def test_parses_and_finds_first_crossover(self):
        result = parse_result(valid_result())

        self.assertEqual(result["8502_mhz"], 2)
        self.assertIsNone(
            result["crossovers"]["copy"]["8502_executive_offload_to_z80"]
        )
        self.assertEqual(
            result["crossovers"]["copy"]["z80_executive_offload_to_8502"][
                "size"
            ],
            256,
        )

    def test_rejects_incomplete_result(self):
        block = valid_result()
        block[5] = 0x80
        block[11] = 4

        with self.assertRaisesRegex(ValueError, "timer-overflow"):
            parse_result(block)

    def test_rejects_partial_validation(self):
        block = valid_result()
        block[33] = 0x07

        with self.assertRaisesRegex(ValueError, "validation mask"):
            parse_result(block)

    def test_rejects_wrong_checksum(self):
        block = valid_result()
        block[32 + 12] ^= 1

        with self.assertRaisesRegex(ValueError, "checksum pair"):
            parse_result(block)

    def test_rejects_timer_overflow_sentinel(self):
        block = valid_result()
        block[32 + 4 : 32 + 6] = b"\xff\xff"

        with self.assertRaisesRegex(ValueError, "invalid"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

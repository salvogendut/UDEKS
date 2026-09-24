# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from context_decode import parse_result  # noqa: E402


def valid_result(cpu: int = 2) -> bytearray:
    block = bytearray(128)
    block[:4] = b"CTXB"
    block[4] = 1
    block[5] = cpu
    block[6] = 2
    block[7] = 4
    block[8] = 8
    block[10:12] = (64).to_bytes(2, "little")
    block[12:15] = bytes((16, 16, 24) if cpu == 2 else (7, 33, 33))
    medians = (100, 740, 740, 868)
    for variant_index, value in enumerate(medians):
        for sample_index in range(8):
            offset = 32 + variant_index * 16 + sample_index * 2
            block[offset : offset + 2] = (value + sample_index).to_bytes(2, "little")
    return block


class ContextDecodeTests(unittest.TestCase):
    def test_parses_and_subtracts_matching_empty_samples(self):
        result = parse_result(valid_result())

        self.assertEqual(result["cpu"], "z80")
        self.assertEqual(result["variants"][2]["context_bytes"], 16)
        self.assertEqual(
            result["variants"][2]["ticks_per_save_restore"]["median"], 10.0
        )
        self.assertEqual(
            result["variants"][3]["ticks_per_save_restore"]["median"], 12.0
        )

    def test_accepts_8502_context_shape(self):
        result = parse_result(valid_result(cpu=1))

        self.assertEqual(result["cpu"], "8502")
        self.assertEqual(result["variants"][2]["context_bytes"], 33)

    def test_rejects_wrong_context_shape(self):
        block = valid_result()
        block[14] = 23

        with self.assertRaisesRegex(ValueError, "context sizes"):
            parse_result(block)

    def test_rejects_qualification_failure(self):
        block = valid_result()
        block[15] = 1

        with self.assertRaisesRegex(ValueError, "qualification failure"):
            parse_result(block)

    def test_rejects_timer_overflow(self):
        block = valid_result()
        block[64:66] = b"\xff\xff"

        with self.assertRaisesRegex(ValueError, "overflowed"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

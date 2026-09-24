# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from irq_probe_decode import parse_result  # noqa: E402


def valid_result() -> bytearray:
    block = bytearray(128)
    block[:4] = b"IRQP"
    block[4] = 1
    block[5] = 2
    block[6] = 2
    block[7] = 2
    block[8:10] = (32).to_bytes(2, "little")
    block[10:12] = (32).to_bytes(2, "little")
    block[14] = 0x81
    block[15] = 0x81
    block[16:18] = (1000).to_bytes(2, "little")
    block[18:20] = (32).to_bytes(2, "little")
    for index, sample in enumerate(range(20, 52)):
        offset = 32 + index * 2
        block[offset : offset + 2] = sample.to_bytes(2, "little")
    return block


class IrqProbeDecodeTests(unittest.TestCase):
    def test_parses_valid_probe(self):
        result = parse_result(valid_result())

        self.assertEqual(result["cpu"], "z80")
        self.assertEqual(result["mode"], "z80-im1")
        self.assertEqual(result["interrupts_observed"], 32)
        self.assertEqual(result["latency_min_ticks"], 20)
        self.assertEqual(result["latency_median_ticks"], 35.5)
        self.assertEqual(result["latency_max_ticks"], 51)

    def test_rejects_wrong_count(self):
        block = valid_result()
        block[10] = 31

        with self.assertRaisesRegex(ValueError, "expected 32"):
            parse_result(block)

    def test_rejects_wrong_source(self):
        block = valid_result()
        block[12] = 1

        with self.assertRaisesRegex(ValueError, "unexpected"):
            parse_result(block)

    def test_rejects_wrong_icr(self):
        block = valid_result()
        block[15] = 0x80

        with self.assertRaisesRegex(ValueError, "ICR"):
            parse_result(block)

    def test_rejects_wrong_sample_count(self):
        block = valid_result()
        block[18] = 31

        with self.assertRaisesRegex(ValueError, "sample count"):
            parse_result(block)

    def test_rejects_sample_longer_than_period(self):
        block = valid_result()
        block[32:34] = (1001).to_bytes(2, "little")

        with self.assertRaisesRegex(ValueError, "exceeds timer period"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

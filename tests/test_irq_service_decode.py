# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from irq_service_decode import parse_result  # noqa: E402


def valid_result() -> bytearray:
    block = bytearray(320)
    block[:4] = b"IRQS"
    block[4] = 1
    block[5] = 2
    block[6] = 2
    block[7] = 2
    block[8] = 3
    block[9] = 16
    block[10:12] = (48).to_bytes(2, "little")
    block[12:14] = (48).to_bytes(2, "little")
    block[16] = 0x81
    block[17] = 0x81
    block[18:20] = (4000).to_bytes(2, "little")
    block[24:28] = (16).to_bytes(4, "little")
    block[28] = 1
    block[29] = 16
    for index in range(48):
        variant = index // 16
        entry = 20 + (index % 4)
        preexit = entry + 30 + variant
        resume = preexit + 15
        offset = 32 + index * 2
        block[offset : offset + 2] = entry.to_bytes(2, "little")
        offset = 128 + index * 2
        block[offset : offset + 2] = preexit.to_bytes(2, "little")
        offset = 224 + index * 2
        block[offset : offset + 2] = resume.to_bytes(2, "little")
    return block


class IrqServiceDecodeTests(unittest.TestCase):
    def test_parses_all_variants_and_derived_costs(self):
        result = parse_result(valid_result())

        self.assertEqual(result["cpu"], "z80")
        self.assertEqual(len(result["variants"]), 3)
        self.assertEqual(
            result["variants"][0]["instrumented_handler"]["median_ticks"], 30.0
        )
        self.assertEqual(
            result["variants"][2]["preexit_to_resume"]["maximum_ticks"], 15
        )
        self.assertEqual(
            result["variants"][1]["entry_to_resume"]["median_ticks"], 46.0
        )

    def test_rejects_incomplete_interrupt_count(self):
        block = valid_result()
        block[12] = 47

        with self.assertRaisesRegex(ValueError, "expected 48"):
            parse_result(block)

    def test_rejects_failed_tick_work(self):
        block = valid_result()
        block[24] = 15

        with self.assertRaisesRegex(ValueError, "kernel-tick counter"):
            parse_result(block)

    def test_rejects_failed_dispatch_work(self):
        block = valid_result()
        block[29] = 15

        with self.assertRaisesRegex(ValueError, "dispatch target"):
            parse_result(block)

    def test_rejects_non_monotonic_sample(self):
        block = valid_result()
        block[128:130] = (10).to_bytes(2, "little")

        with self.assertRaisesRegex(ValueError, "not monotonic"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

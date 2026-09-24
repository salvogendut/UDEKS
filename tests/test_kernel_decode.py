# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from kernel_decode import expected_checksums, parse_result  # noqa: E402


def valid_result(cpu: int = 2, configuration: int = 3) -> bytearray:
    block = bytearray(128)
    block[:4] = b"KPRM"
    block[4] = 1
    block[5] = cpu
    block[6] = configuration
    block[7] = 7
    block[8] = 2
    block[9] = 8
    block[10] = 1
    iterations = (1, 128, 128, 32, 128, 128, 128)
    for index, (case_id, checksum) in enumerate(expected_checksums().items()):
        offset = 16 + index * 8
        block[offset] = case_id
        block[offset + 2 : offset + 4] = iterations[index].to_bytes(2, "little")
        block[offset + 4 : offset + 6] = (100 + index).to_bytes(2, "little")
        block[offset + 6 : offset + 8] = checksum.to_bytes(2, "little")
    return block


class KernelDecodeTests(unittest.TestCase):
    def test_parses_complete_valid_result(self):
        result = parse_result(valid_result())

        self.assertEqual(result["cpu"], "z80")
        self.assertEqual(result["configuration"], 3)
        self.assertEqual(result["records"][3]["name"], "event_queue")

    def test_accepts_8502_speed_identifiers(self):
        self.assertEqual(parse_result(valid_result(1, 1))["configuration"], 1)
        self.assertEqual(parse_result(valid_result(1, 2))["configuration"], 2)

    def test_rejects_wrong_checksum(self):
        block = valid_result()
        block[16 + 3 * 8 + 6] ^= 1

        with self.assertRaisesRegex(ValueError, "checksum"):
            parse_result(block)

    def test_rejects_wrong_cpu_configuration(self):
        block = valid_result()
        block[6] = 2

        with self.assertRaisesRegex(ValueError, "Z80 configuration"):
            parse_result(block)

    def test_rejects_timer_overflow(self):
        block = valid_result()
        block[16 + 4 : 16 + 6] = b"\xff\xff"

        with self.assertRaisesRegex(ValueError, "overflowed"):
            parse_result(block)


if __name__ == "__main__":
    unittest.main()

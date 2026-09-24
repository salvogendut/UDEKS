# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from boot_chain_decode import parse_result


def valid_record() -> bytearray:
    block = bytearray(48)
    block[:13] = b"UMMU\x01\x02\x3e\x09\x00\xf0\x01\xf0\x37"
    block[16:28] = b"S0OKS1OKZ80!"
    block[28:36] = b"\x02\x00\x3f\x08\x3f\x08\xd4\x01"
    return block


class BootChainDecodeTests(unittest.TestCase):
    def test_accepts_complete_native_boot(self):
        result = parse_result(valid_record())
        self.assertEqual(result["blocks"], 212)
        self.assertEqual(result["z80_checksum"], 0x083F)

    def test_rejects_missing_stage_marker(self):
        block = valid_record()
        block[20:24] = b"FAIL"
        with self.assertRaisesRegex(ValueError, "stage-1"):
            parse_result(block)

    def test_reports_loader_failure(self):
        block = valid_record()
        block[28] = 0x84
        block[29] = 4
        with self.assertRaisesRegex(ValueError, "code 0x04"):
            parse_result(block)

    def test_rejects_z80_checksum_mismatch(self):
        block = valid_record()
        block[32] = 0x40
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            parse_result(block)

    def test_preserved_emulator_records_pass(self):
        result_root = ROOT / "bench/results/2026-09-24-native-boot/raw"
        for name in ("vice-3.10.bin", "1986-7556c23.bin"):
            with self.subTest(result=name):
                result = parse_result((result_root / name).read_bytes())
                self.assertEqual(result["loader_state"], 2)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from service_registry_decode import parse_result


def valid_record() -> bytearray:
    return bytearray(
        b"SREG\x01\x02\x00\x01\x01\x00\x01\x00\x00\x00\x01\x10"
        b"\x03\x01\x00\x00\x00\x00\x00\x00"
    )


class ServiceRegistryDecodeTests(unittest.TestCase):
    def test_accepts_started_console_service(self):
        result = parse_result(valid_record())
        self.assertEqual(result["started"], 1)
        self.assertEqual(result["last_class"], 1)
        self.assertEqual(result["last_flags"], 3)
        self.assertEqual(result["poll_passes"], 0)
        self.assertEqual(result["polled_services"], 0)

    def test_reports_poll_diagnostics(self):
        block = valid_record()
        block[18:20] = b"\x34\x12"
        block[23] = 1
        result = parse_result(block)
        self.assertEqual(result["poll_passes"], 0x1234)
        self.assertEqual(result["polled_services"], 1)

    def test_reports_registry_failure(self):
        block = valid_record()
        block[5] = 0x87
        block[6] = 7
        with self.assertRaisesRegex(ValueError, "code 0x07"):
            parse_result(block)

    def test_rejects_inconsistent_counts(self):
        block = valid_record()
        block[8] = 0
        with self.assertRaisesRegex(ValueError, "counts disagree"):
            parse_result(block)

    def test_rejects_wrong_abi(self):
        block = valid_record()
        block[14] = 2
        with self.assertRaisesRegex(ValueError, "ABI 0.2"):
            parse_result(block)

    def test_preserved_emulator_records_pass(self):
        result_root = ROOT / "bench/results/2026-09-24-service-registry/raw"
        for name in ("vice-3.10.bin", "1986-7556c23.bin"):
            with self.subTest(result=name):
                result = parse_result((result_root / name).read_bytes())
                self.assertEqual(result["started"], 1)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from capability_decode import parse_result


def record(
    video: int = 1,
    revision: int = 2,
    ram: int = 64,
    reu: int = 0,
    georam: int = 0,
) -> bytearray:
    family = 2 if revision >= 2 else 1
    flags = (1 if video == 1 else 2) | (4 if ram == 64 else 0)
    flags |= 8 if reu else 0
    flags |= 16 if georam else 0
    flags |= 32 if family == 2 else 0
    return bytearray(
        b"HCAP"
        + bytes((1, 2, 0, video, revision, family, ram, flags, reu, georam,
                 family, 0x1F, 0x2F))
        + bytes(15)
    )


class CapabilityDecodeTests(unittest.TestCase):
    def test_accepts_pal_8568_64k(self):
        result = parse_result(record())
        self.assertEqual(result["video_standard"], 1)
        self.assertEqual(result["vdc_ram_kib"], 64)

    def test_accepts_ntsc_8563_16k(self):
        result = parse_result(record(video=2, revision=1, ram=16))
        self.assertEqual(result["video_standard"], 2)
        self.assertEqual(result["vdc_family"], 1)

    def test_accepts_each_supported_expansion(self):
        self.assertEqual(parse_result(record(reu=1))["reu_present"], 1)
        self.assertEqual(parse_result(record(georam=1))["georam_present"], 1)

    def test_rejects_inconsistent_flags(self):
        block = record()
        block[11] = 0
        with self.assertRaisesRegex(ValueError, "capability flags"):
            parse_result(block)

    def test_rejects_incomplete_probe(self):
        block = record()
        block[15] = 0x0F
        with self.assertRaisesRegex(ValueError, "completion mask"):
            parse_result(block)

    def test_preserved_profiles_pass(self):
        result_root = ROOT / "bench/results/2026-09-24-capabilities/raw"
        expected = {
            "vice-pal64.bin": (1, 64, 0, 0),
            "vice-ntsc16.bin": (2, 16, 0, 0),
            "vice-reu512.bin": (1, 64, 1, 0),
            "vice-georam512.bin": (1, 64, 0, 1),
            "1986-64.bin": (1, 64, 0, 0),
            "1986-16.bin": (1, 16, 0, 0),
        }
        for name, values in expected.items():
            with self.subTest(profile=name):
                result = parse_result((result_root / name).read_bytes())
                self.assertEqual(
                    (
                        result["video_standard"],
                        result["vdc_ram_kib"],
                        result["reu_present"],
                        result["georam_present"],
                    ),
                    values,
                )


if __name__ == "__main__":
    unittest.main()

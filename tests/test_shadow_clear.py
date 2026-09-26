# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from shadow_clear_decode import (
    SHADOW_SIZE,
    compare_shadow_bitmap,
    parse_window,
)


RAW = ROOT / "bench/results/2026-09-26-shadow-clear/raw"

# Layout of the preserved 2026-09-26 build: the sequential 8,000-byte
# VICSHADOW segment sits at $AB2D-$CA6C, the reclaimed tail runs to the fixed
# SYSCALLS page at $CF00, boot staging starts at $AF00, and the live probe and
# crt0 staging pages sit at $AD00-$ADFF and $AE00-$AEFF.
SHADOW_START = 0xAB2D
STAGING_START = 0xAF00
PROBE_STAGING_ADDRESS = 0xAD00
PROBE_SIZE = 0x0100
CRT0_STAGING_ADDRESS = 0xAE00
CRT0_SIZE = 0x0100


class ShadowClearEvidenceTests(unittest.TestCase):
    def test_preserved_boot_clears_the_whole_shadow_and_keeps_the_tail(self):
        window = (RAW / "shadow-after-boot.bin").read_bytes()
        preimage = (RAW / "shadow-preimage.bin").read_bytes()
        result = parse_window(window, preimage, SHADOW_START, SHADOW_SIZE)
        self.assertEqual(len(window), 0xCF00 - SHADOW_START)
        self.assertEqual(len(preimage), len(window))
        self.assertTrue(result["shadow_cleared"])
        self.assertTrue(result["tail_intact"])
        self.assertEqual(
            result["tail_size"], 0xCF00 - SHADOW_START - SHADOW_SIZE
        )

    def test_preimage_seeds_the_reclaimed_prefix(self):
        preimage = (RAW / "shadow-preimage.bin").read_bytes()
        prefix = preimage[: PROBE_STAGING_ADDRESS - SHADOW_START]
        self.assertTrue(prefix)
        self.assertTrue(all(byte != 0 for byte in prefix))
        for address, size in (
            (PROBE_STAGING_ADDRESS, PROBE_SIZE),
            (CRT0_STAGING_ADDRESS, CRT0_SIZE),
        ):
            staged = preimage[
                address - SHADOW_START : address - SHADOW_START + size
            ]
            self.assertTrue(any(byte != 0 for byte in staged))

    def test_preserved_repaint_matches_the_bank1_bitmap(self):
        shadow = (RAW / "shadow-drawn.bin").read_bytes()
        bitmap = (RAW / "vic-bitmap.bin").read_bytes()
        self.assertEqual(len(shadow), SHADOW_SIZE)
        self.assertEqual(len(bitmap), SHADOW_SIZE)
        self.assertEqual(compare_shadow_bitmap(shadow, bitmap), [])

    def test_decoder_rejects_a_truncated_window(self):
        preimage = (RAW / "shadow-preimage.bin").read_bytes()
        with self.assertRaisesRegex(ValueError, "truncated"):
            parse_window(
                bytes(SHADOW_SIZE - 1),
                preimage[: SHADOW_SIZE - 1],
                SHADOW_START,
                SHADOW_SIZE,
            )

    def test_decoder_rejects_a_late_clear(self):
        window = bytearray((RAW / "shadow-after-boot.bin").read_bytes())
        preimage = (RAW / "shadow-preimage.bin").read_bytes()
        window[0] = 0x11
        result = parse_window(
            bytes(window), preimage, SHADOW_START, SHADOW_SIZE
        )
        self.assertFalse(result["shadow_cleared"])
        self.assertTrue(result["tail_intact"])

    def test_decoder_rejects_a_clobbered_tail(self):
        window = bytearray((RAW / "shadow-after-boot.bin").read_bytes())
        preimage = (RAW / "shadow-preimage.bin").read_bytes()
        window[SHADOW_SIZE + 10] = 0
        result = parse_window(
            bytes(window), preimage, SHADOW_START, SHADOW_SIZE
        )
        self.assertTrue(result["shadow_cleared"])
        self.assertFalse(result["tail_intact"])
        self.assertEqual(result["tail_mismatches"], [10])


class ShadowClearSourceTests(unittest.TestCase):
    def test_crt0_clears_the_shadow_through_linker_bounds(self):
        crt0 = (ROOT / "src/8502/crt0.s").read_text(encoding="utf-8")
        self.assertIn(".import __VICSHADOW_RUN__, __VICSHADOW_SIZE__", crt0)
        self.assertIn("ldx #>__VICSHADOW_SIZE__", crt0)
        self.assertIn("sta (CLEAR_POINTER),y", crt0)

    def test_stage1_leaves_the_reclaimed_tail_alone(self):
        stage1 = (ROOT / "src/boot/stage1-gateway.s").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("final_clear_vic_shadow", stage1)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from boot_banner_probe import fixture


class BootBanner(unittest.TestCase):
    def test_fault_fixture_changes_only_identity_bytes(self):
        original = (ROOT/'bench/artifacts/2026-09-30-default-mount/udeks.d64').read_bytes()
        self.assertEqual(fixture(original, 'normal'), original)
        changed = {}
        for variant in ('iec', 'bootfs', 'both'):
            image = fixture(original, variant)
            changed[variant] = {i for i, (a, b) in enumerate(zip(original, image)) if a != b}
            self.assertEqual(len(changed[variant]), 2 if variant == 'both' else 1)
        self.assertEqual(changed['both'], changed['iec'] | changed['bootfs'])
        with self.assertRaises(ValueError): fixture(bytes(len(original)), 'normal')

    def test_banner_uses_measured_flags_and_never_claims_a_mount(self):
        source = (ROOT/'src/services/window/boot_console.c').read_text()
        self.assertNotIn('SERVICES : DEFERRED', source)
        for macro in ('UDEKS_BOOT_CHAIN_IEC_HEADER', 'UDEKS_BOOT_CHAIN_BOOTFS_HEADER'):
            self.assertIn(macro+') == 1 ?', source)
        gateway = (ROOT/'src/boot/stage1-gateway.s').read_text()
        check = gateway.split('checksum_high_matches:', 1)[1].split('bootfs_checked:', 1)[0]
        self.assertNotIn('sta MMU_LCR_KERNEL_FLAT', check)
        self.assertIn('stx BOOT_CHAIN+21', check)
        self.assertIn('stx BOOT_CHAIN+22', check)
        self.assertIn('lda $1203,y', check)
        self.assertIn('lda $a000,y', check)
        self.assertEqual(check.count('ldy #$05'), 2)

    def test_normal_boot_keeps_the_hardware_tested_progress_setting(self):
        source = (ROOT/'src/boot/stage1.s').read_text().split('secondary_payload_load:', 1)[1]
        self.assertIn('lda #$ff\n        jsr $ff90', source)


if __name__ == '__main__': unittest.main()

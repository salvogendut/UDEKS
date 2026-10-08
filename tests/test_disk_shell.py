# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_d71 import blank_d71, d64_compatibility_image, install_prg_file
from build_udex import build_executable
from disk_shell_fixture import build_fixture, shell_file


class DiskShellFixture(unittest.TestCase):
    def setUp(self):
        self.base = blank_d71()
        self.program = build_executable(b'X'*250+b'UDEKS 0.1.0 c128 8502'+b'\0',
            cpu=1, load_address=0x9000, entry_address=0x9000, flags=1)
        install_prg_file(self.base, 'USH', self.program, file_type=0x81)

    def test_variants_change_only_disk_shell_not_boot_payload(self):
        for image in (self.base, d64_compatibility_image(self.base)):
            original = bytes(image)
            entry, offsets = shell_file(image)
            for variant in ('diskA', 'diskB', 'bad', 'missing', 'entry', 'flags'):
                result = build_fixture(image, variant)
                self.assertEqual(bytes(image), original)
                self.assertEqual(len(result), len(image))
                changed = {p for p, (a, b) in enumerate(zip(image, result)) if a != b}
                self.assertTrue(changed)
                self.assertLessEqual(changed, {entry} if variant == 'missing' else set(offsets))
                payload = bytes(result[p] for p in offsets)
                if variant.startswith('disk'):
                    self.assertIn(('UDEKS '+variant+' c128 8502').encode(), payload)
                    self.assertEqual(payload[:16], self.program[:16])
                elif variant == 'bad': self.assertEqual(payload[0], 0)
                elif variant == 'entry': self.assertEqual(payload[14], 1)
                elif variant == 'flags': self.assertEqual(payload[7], 0)
                else: self.assertEqual(result[entry], 0)

    def test_bad_fixture_inputs_fail_closed(self):
        with self.assertRaises(ValueError): shell_file(blank_d71())
        with self.assertRaises(ValueError): build_fixture(self.base, 'unknown')
        damaged = bytearray(self.base)
        _, offsets = shell_file(damaged)
        damaged[offsets[0]] = 0
        with self.assertRaises(ValueError): build_fixture(damaged, 'diskA')
        first = offsets[0]-2
        entry, _ = shell_file(self.base)
        damaged[first:first+2] = damaged[entry+1:entry+3]
        with self.assertRaises(ValueError): shell_file(damaged)

    def test_bootstrap_stays_in_private_loader_segments(self):
        source = (ROOT/'src/boot/stage1-gateway.s').read_text()
        self.assertIn('task_loader_end <= $fe20', source)
        self.assertIn('boot_shell_entry = $fe80', source)
        self.assertIn('* <= $ff00', source)
        self.assertIn('lda $ba\n        sta BOOT_CHAIN+20', source)
        policy = source[source.index('boot_shell_policy:'):]
        self.assertIn('lda #18', policy)  # release bootstrap mount
        self.assertIn('sta BOOT_SHELL_ERROR', policy)
        self.assertIn('boot_shell_fallback:', policy)
        gate = source[source.index('boot_shell_entry:'):source.index('boot_shell_policy:')]
        self.assertIn('cmp task_lookup_signature,x', gate)
        self.assertIn('plp\n        cmp #0', gate)  # init branches on Z
        self.assertIn('sta boot_saved_activation,x', gate)
        self.assertIn('lda boot_saved_activation,x', gate)
        self.assertIn('sta $f68a,x', gate)
        from build_d71 import TASK_SWITCH_ACTIVATION_SIZE
        self.assertIn(f'BOOT_ACTIVATION_SIZE = {TASK_SWITCH_ACTIVATION_SIZE}', source)
        self.assertIn('task_persistent_entry_bad:\n        jmp task_bad_entry', source)

    def test_boot_root_requests_rw_but_clears_flags_before_later_requests(self):
        source = (ROOT/'src/boot/stage1-gateway.s').read_text()
        mount = source.split('boot_shell_device_ready:', 1)[1].split('boot_shell_mounted:', 1)[0]
        self.assertIn('lda #14', mount)
        self.assertIn('sta DISK_REQUEST+5', mount)
        self.assertIn('lda #1', mount)
        self.assertIn('sta DISK_REQUEST+13', mount)
        self.assertLess(mount.index('jsr boot_shell_request'), mount.index('stx DISK_REQUEST+13'))
        self.assertLess(mount.index('stx DISK_REQUEST+13'), mount.index('cmp #0'))
        self.assertLess(mount.index('cmp #0'), mount.index('beq boot_shell_mounted'))


if __name__ == '__main__': unittest.main()

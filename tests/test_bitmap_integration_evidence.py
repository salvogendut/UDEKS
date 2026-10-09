# SPDX-License-Identifier: GPL-3.0-or-later
"""Installed bitmap service evidence, separate from the earlier private proof."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_window_cache import layout_maps
from placement_audit import parse_map

EVIDENCE = ROOT / 'bench/results/2026-10-09-bitmap-integration'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BitmapIntegrationEvidence(unittest.TestCase):
    def setUp(self):
        self.report = json.loads((EVIDENCE / 'report.json').read_text())

    def test_manifest_and_target_artifacts(self):
        named = set()
        for line in (EVIDENCE / 'SHA256SUMS').read_text().splitlines():
            expected, name = line.split('  ', 1)
            self.assertNotIn(name, named)
            named.add(name)
            self.assertEqual(digest(EVIDENCE / name), expected, name)
        self.assertEqual(named, {str(p.relative_to(EVIDENCE))
            for p in EVIDENCE.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'})
        for original, saved in (
            ('build/bitmap-store/retained-check', 'sim6502/check'),
            ('build/bitmap-store/retained-check.map', 'sim6502/check.map'),
            ('build/8502/udeks-8502.map', 'maps/normal.map'),
            ('build/8502/udeks-8502-panic-probe.map', 'maps/panic.map')):
            self.assertEqual(digest(EVIDENCE / saved),
                             self.report['source_and_build_sha256'][original])
        self.assertEqual(self.report['target_checks'], 22462)
        self.assertEqual((EVIDENCE / 'sim6502/check.log').read_text(),
            'PASS 22462 retained bitmap checks: shared allocator, request parity and pixels\n')

    def test_installed_modules_and_unchanged_reservations(self):
        normal = (EVIDENCE / 'maps/normal.map').read_text()
        segments = layout_maps(normal, (EVIDENCE / 'maps/panic.map').read_text())
        modules, _ = parse_map(normal)
        self.assertNotIn('bitmap_store.o', modules)
        self.assertEqual(modules['retained_pool.o'], dict(BSS=5, GRAPHICSCODE=154))
        for name, code, bss in (('retained_bitmap.o', 978, 16),
                                ('retained_bitmap_paint.o', 196, 13)):
            self.assertEqual((modules[name]['CODE'], modules[name]['BSS']), (code, bss))
        self.assertEqual((self.report['pool_address'], self.report['pool_bytes']), (0x1300, 2304))
        self.assertEqual(segments['BSS'][1], 0x93ad)
        self.assertEqual(self.report['resident_free_bytes'], 0x93d0 - segments['BSS'][1] - 1)
        self.assertEqual(self.report['resident_free_bytes'], 34)
        self.assertEqual(self.report['graphics_segment_free'], 0x1300 - segments['GRAPHICSCODE'][1] - 1)
        self.assertEqual(self.report['path_segment_free'], 0x9aa8 - segments['GRAPHICSPATHS'][1] - 1)

    def test_public_clients_use_qualified_disks_and_same_program(self):
        for fmt, drive in (('d71', '1571'), ('d81', '1581')):
            result = json.loads((EVIDENCE / f'vice/api-{fmt}/result.json').read_text())
            self.assertEqual(result['drive'], drive)
            self.assertEqual(result['abi_minor'], 20)
            self.assertEqual(result['disk_sha256'], self.report['disk_sha256'][fmt])
            self.assertEqual(result['program_sha256'], digest(EVIDENCE / 'client/BMAP.BIN'))
            self.assertEqual(result['retirement'], ['close', 'abort', 'exit', 'cancel'])
            self.assertEqual(result['future_version_rejected'], 21)
            self.assertEqual(result['older_bitmap_version_rejected'], 19)
            self.assertEqual(result['checks'][-1]['command'], 'echo bitmap API passed')

    def test_captured_pixels_match_independent_oracle(self):
        cases = (('normal', 24, 34, 128, 80), ('moved', 54, 64, 128, 80),
                 ('uncovered', 54, 64, 128, 80), ('peer', 24, 34, 32, 24),
                 ('wide', 24, 34, 160, 100), ('odd', 24, 34, 9, 7),
                 ('pending', 24, 34, 128, 80))
        for fmt in ('d71', 'd81'):
            for tag, x, y, width, height in cases:
                with self.subTest(disk=fmt, case=tag):
                    base = EVIDENCE / f'vice/api-{fmt}'
                    shadow = (base / f'{tag}-shadow.bin').read_bytes()
                    bitmap = (base / f'{tag}-bitmap.bin').read_bytes()
                    self.assertEqual((len(shadow), len(bitmap)), (8002, 8002))
                    self.assertEqual((shadow[:2], bitmap[:2]), (b'\xe0\xa1', b'\0\x60'))
                    self.assertEqual(shadow[2:], bitmap[2:])
                    for yy in range(height):
                        for xx in range(width):
                            offset = yy * ((width + 7) // 8) + xx // 8
                            expected = tag != 'pending' and bool(((offset * 37 + 11) & 255) & (128 >> (xx % 8)))
                            cell = ((y + yy) // 8) * 320 + ((x + xx) // 8) * 8 + (y + yy) % 8
                            actual = bool(bitmap[2 + cell] & (128 >> ((x + xx) % 8)))
                            self.assertEqual(actual, expected, (tag, xx, yy))

    def test_pool_survives_movement_oom_and_peer_compaction(self):
        base = EVIDENCE / 'vice/api-d71'
        normal = (base / 'normal-image.bin').read_bytes()[2:]
        self.assertEqual(normal[:8], bytes((4, 0, 14, 128, 80, 16, 0, 5)))
        self.assertEqual(normal[8:], bytes((i * 37 + 11) & 255 for i in range(1280)))
        for tag in ('after-move', 'after-oom'):
            self.assertEqual((base / f'{tag}-image.bin').read_bytes()[2:], normal)
        self.assertEqual((base / 'peer-before-image.bin').read_bytes()[2:],
                         (base / 'peer-after-image.bin').read_bytes()[2:])
        for tag in ('aborted', 'cancelled', 'exit', 'closed'):
            self.assertEqual((base / f'{tag}-lengths.bin').read_bytes()[2:], bytes(8))

    def test_existing_four_app_input_regressions(self):
        vice = json.loads((EVIDENCE / 'vice/four-native-d71.json').read_text())
        native = json.loads((EVIDENCE / '1986/four-native-d81.json').read_text())
        self.assertEqual(vice['disk_sha256'], self.report['disk_sha256']['d71'])
        self.assertEqual(native['disk_sha256'], self.report['disk_sha256']['d81'])
        self.assertEqual(vice['checks'][-1]['command'], 'echo four-slot cleanup passed')
        self.assertEqual(native['exit_status'], 0)
        self.assertTrue(native['four_native'])
        self.assertIn('PASS four native:', (EVIDENCE / '1986/four-native-d81.log').read_text())


if __name__ == '__main__':
    unittest.main()

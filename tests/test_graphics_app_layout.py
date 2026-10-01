# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from graphics_app_layout import CANDIDATE, Region, disjoint, managed_size, worker_image, z80_regions


class GraphicsAppLayoutTests(unittest.TestCase):
    def test_proposed_slots_stacks_and_pages_are_disjoint(self):
        disjoint(list(CANDIDATE))
        self.assertEqual([r.limit-r.start for r in CANDIDATE],
                         [4608, 2816, 768, 768, 512, 512])
        # Physical bank is part of ownership; equal logical ranges may coexist.
        disjoint([Region('a', 0, 0x2300, 0x3500), CANDIDATE[0]])

    def test_each_one_byte_overlap_is_rejected(self):
        for i, region in enumerate(CANDIDATE):
            with self.subTest(region=region.name):
                with self.assertRaisesRegex(ValueError, 'overlap'):
                    disjoint(list(CANDIDATE) + [Region('intruder', region.bank, region.limit-1, region.limit)])
        with self.assertRaisesRegex(ValueError, 'overlap'):
            disjoint([replace(CANDIDATE[0], limit=CANDIDATE[1].start+1), CANDIDATE[1]])

    def test_common_ram_and_invalid_physical_bounds_reject(self):
        for region in (Region('bad', 2, 0, 1), Region('bad', 0, 0, 0),
                       Region('bad', 0, 0xFFFF, 0x10001),
                       Region('bad', 1, 0xEFFF, 0xF001)):
            with self.assertRaises(ValueError):
                disjoint([region])

    def test_worker_code_growth_and_nonempty_data_are_not_free(self):
        text = ' 00002000 s__CODE\n 00000297 l__CODE\n 00003000 s__DATA\n 00000000 l__DATA\n'
        regions = z80_regions(text)
        self.assertEqual(regions, [Region('Z80 CODE', 1, 0x2000, 0x2297)])
        disjoint(regions + list(CANDIDATE))
        for changed in (text.replace('00000297', '00000301'),
                        text.replace('00000000 l__DATA', '00000001 l__DATA')):
            with self.assertRaisesRegex(ValueError, 'overlap'):
                disjoint(z80_regions(changed) + list(CANDIDATE))

    def test_missing_or_conflicting_worker_area_symbols_reject(self):
        text = ' 00002000 s__CODE\n 00000297 l__CODE\n'
        for changed in ('', text + ' 00003000 s__DATA\n',
                        text + ' 00000400 l__CODE\n'):
            with self.assertRaises(ValueError):
                z80_regions(changed)

    def test_zero_padding_is_not_emitted_code_and_disagreement_rejects(self):
        regions = [Region('code', 1, 0x2000, 0x2002)]
        data = bytes([0xF3, 0xC9]) + bytes(8190)
        worker_image(regions, {0x2000: 0xF3, 0x2001: 0xC9}, data)
        for image, padded in (({0x2300: 0}, data), ({0x2000: 0xEA}, data),
                              ({0x2000: 0xF3, 0x2001: 0xC9}, data[:-1]+b'\x01'),
                              ({}, b'')):
            with self.assertRaises(ValueError):
                worker_image(regions, image, padded)

    def test_real_calculator_allocation_is_not_a_bank_1_execution_proof(self):
        data = (ROOT / 'bench/artifacts/2026-09-30-xcalc/xcalc.udx').read_bytes()
        result = managed_size(data)
        self.assertEqual(result, dict(load=0x200, image=3993, bss=34, allocation=4027))
        self.assertEqual(4608-result['allocation'], 581)
        for offset, value in ((7, 0), (16, 0), (14, 0xFF)):
            changed = bytearray(data)
            changed[offset] = value
            with self.assertRaises(ValueError):
                managed_size(changed)
        with self.assertRaises(ValueError):
            managed_size(data+b'\0')

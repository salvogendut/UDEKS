# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from graphics_pixel_bench import decode, reference, compare, replace_pixel
from graphics_raster_audit import REFERENCE_SOURCE
from graphics_raster_bench_build import function


class GraphicsPixelTests(unittest.TestCase):
    def test_replacement_changes_only_the_public_pixel_entry(self):
        source = REFERENCE_SOURCE.read_text()
        old = function(source, 'udeks_vic_bitmap_pixel').rstrip()
        self.assertEqual(replace_pixel(source).replace(
            '/* Pixel entry supplied by the isolated ASM object. */', old), source)
        with self.assertRaises(ValueError):
            replace_pixel('')

    def test_decoder_checks_stack_guards_pixels_dirty_and_completion(self):
        for case in range(4):
            data = bytearray(64) + bytearray(reference(case))
            data[:8] = b'PIXL\x01\x02' + bytes((1, case))
            data[8:12] = (123).to_bytes(4, 'little')
            data[12:15] = b'\x5a\xa5\xc3'
            self.assertEqual(decode(data, 1, case), 123)
            for offset in (0, 5, 6, 7, 12, 13, 14, 15, 63, 64, 8064, 8065):
                broken = data[:]; broken[offset] ^= 1
                with self.subTest(case=case, offset=offset), self.assertRaises(ValueError):
                    decode(broken, 1, case)
            with self.assertRaises(ValueError):
                decode(data[:-1], 1, case)
            data[8:12] = bytes(4)
            with self.assertRaises(ValueError):
                decode(data, 1, case)
        self.assertEqual(reference(2)[8000:], b'\x01\x01' + bytes(30))

    def test_service_uses_the_exact_qualified_assembly(self):
        for bench, installed in (('bench/graphics-pixel/pixel.s', 'vic_pixel.s'),
                                  ('bench/graphics-span/span.s', 'vic_span.s')):
            self.assertEqual((ROOT / bench).read_bytes(),
                             (ROOT / 'src/services/display' / installed).read_bytes())
        source = (ROOT / 'src/services/display/vic_graphics.c').read_text()
        fragment = (ROOT / 'bench/graphics-span/fill.c').read_text()
        self.assertEqual(function(source, 'udeks_vic_bitmap_fill'),
                         function(fragment, 'udeks_vic_bitmap_fill'))
        self.assertNotIn('void udeks_vic_bitmap_pixel(', source)
        pixel = (ROOT / 'src/services/display/vic_pixel.s').read_text()
        self.assertEqual(pixel.count('jmp incsp4'), 2)
        self.assertIn('ldy ptr1+1', pixel)
        self.assertLess(pixel.index('sta $e190,y'), pixel.index('adc #<_udeks_vic_bitmap_shadow'))
        for name in ('pixel', 'span'):
            text = (ROOT / 'src/services/display' / ('vic_' + name + '.s')).read_text()
            self.assertNotRegex(text, r'\bjsr\b|\$(?:d50[0-9]|ff0[0-4])\b')
        irq = (ROOT / 'src/8502/pointer_irq.s').read_text()
        self.assertNotRegex(irq, r'\b(?:ptr1|tmp1|tmp2|_udeks_vic_bitmap_pixel)\b')

    def test_preserved_qualification_and_exact_program_bindings(self):
        artifacts = ROOT / 'bench/artifacts/2026-09-28-graphics-pixel'
        results = ROOT / 'bench/results/2026-09-28-graphics-pixel'
        report = json.loads((artifacts / 'build/build-report.json').read_text())
        self.assertEqual(report['pixel']['CODE'], 190)
        self.assertEqual(report['pixel']['BSS'], 0)
        self.assertEqual(report['object_net_saving'], 87)
        self.assertEqual(report['linked_net_saving'], 87)
        self.assertEqual(report['combined_net_saving'], 173)
        self.assertEqual(report['helpers']['c-reference'], report['helpers']['combined'])
        self.assertEqual(compare(results), json.loads((results / 'report.json').read_text()))
        expected = {f'{label}-{case}.prg' for label in ('c-reference', 'asm-pixel') for case in range(4)}
        self.assertEqual(set(report['program_sha256']), expected)
        for engine in ('1986', 'vice'):
            run = json.loads((results / f'{engine}-run.json').read_text())
            self.assertEqual(run['program_sha256'], report['program_sha256'])
            self.assertEqual(set(run['raw_sha256']),
                {f'{engine}-{label}-{case}.bin' for label in ('c-reference', 'asm-pixel') for case in range(4)})
            for name, sha in run['program_sha256'].items():
                self.assertEqual(hashlib.sha256((artifacts / 'build' / name).read_bytes()).hexdigest(), sha)
            for name, sha in run['raw_sha256'].items():
                self.assertEqual(hashlib.sha256((results / name).read_bytes()).hexdigest(), sha)
        for directory in (artifacts, results):
            for line in (directory / 'SHA256SUMS').read_text().splitlines():
                sha, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), sha, name)

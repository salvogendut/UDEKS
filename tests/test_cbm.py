# SPDX-License-Identifier: GPL-3.0-or-later
"""UDEKS .CBM black-and-white picture container and PNG/JPEG converter."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from png_to_cbm import (MAGIC, VERSION, MAX_HEIGHT, MAX_WIDTH,
                        build, convert, pack_bits, parse, unpack_bits)
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def synthetic(width, height, on):
    image = Image.new('L', (width, height))
    for x, y in on:
        image.putpixel((x, y), 0)
    return image


class CbmFormatTests(unittest.TestCase):
    def test_pack_bits_is_msb_first_and_zeros_low_bits(self):
        self.assertEqual(pack_bits([[1, 0, 1, 0, 0, 0, 0, 0]]), b'\xa0')
        self.assertEqual(pack_bits([[1, 1, 1, 1, 1, 1, 1, 1]]), b'\xff')
        self.assertEqual(pack_bits([[0, 0, 0, 0, 0, 0, 0, 0]]), b'\x00')
        self.assertEqual(pack_bits([[1, 0, 0, 0, 0, 0, 0, 1]]), b'\x81')
        self.assertEqual(pack_bits([[1], [0], [1]]), bytes([0x80, 0x00, 0x80]))

    def test_unpack_bits_round_trips_pack_bits(self):
        rows = [[(x * 7 + y * 13) % 2 for x in range(31)] for y in range(17)]
        self.assertEqual(unpack_bits(pack_bits(rows), 31, 17), rows)

    def test_build_and_parse_header(self):
        payload = bytes(range(24))
        data = build(payload, 32, 6)
        self.assertEqual(data[:4], MAGIC)
        self.assertEqual(data[4], VERSION)
        self.assertEqual((data[5], data[7], data[9]), (32, 6, 4))
        width, height, rows = parse(data)
        self.assertEqual((width, height), (32, 6))
        self.assertEqual(rows, unpack_bits(payload, 32, 6))

    def test_parse_rejects_malformed_files(self):
        valid = build(bytes(1), 8, 1)
        malformed = [
            b'', b'CBM', b'CBM\0', bytes(11),
            valid[:-1], valid + b'X',          # truncated / trailing data
            b'XXX\0' + valid[4:],              # bad magic
            valid[:4] + bytes((2,)) + valid[5:],  # bad version
            b'CBM\0' + bytes((1,)) + (0).to_bytes(2, 'little') +
            (1).to_bytes(2, 'little') + (1).to_bytes(2, 'little') + bytes(1),  # zero width
            b'CBM\0' + bytes((1,)) + (1).to_bytes(2, 'little') +
            (0).to_bytes(2, 'little') + (1).to_bytes(2, 'little') + bytes(1),  # zero height
            b'CBM\0' + bytes((1,)) + (321).to_bytes(2, 'little') +
            (1).to_bytes(2, 'little') + (1).to_bytes(2, 'little') + bytes(1),  # too wide
            b'CBM\0' + bytes((1,)) + (8).to_bytes(2, 'little') +
            (1).to_bytes(2, 'little') + (0).to_bytes(2, 'little') + bytes(1),  # bad stride
            b'CBM\0' + bytes((1,)) + (8).to_bytes(2, 'little') +
            (1).to_bytes(2, 'little') + (1).to_bytes(2, 'little') + bytes(8),   # oversized payload
            b'CBM\0' + bytes((1,)) + (8).to_bytes(2, 'little') +
            (1).to_bytes(2, 'little') + (1).to_bytes(2, 'little') + b'',        # missing payload
        ]
        for bad in malformed:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse(bad)


class ConverterTests(unittest.TestCase):
    def convert(self, image, width=MAX_WIDTH, height=MAX_HEIGHT,
                threshold=128, invert=False):
        directory = tempfile.TemporaryDirectory()
        source = Path(directory.name) / 'in.png'
        target = Path(directory.name) / 'out.CBM'
        image.save(source)
        convert(source, target, width, height, threshold, invert)
        data = target.read_bytes()
        directory.cleanup()
        return parse(data)

    def test_full_screen_solid_white_is_clear(self):
        width, height, rows = self.convert(Image.new('L', (10, 10), 255))
        self.assertEqual((width, height), (MAX_WIDTH, MAX_HEIGHT))
        self.assertTrue(all(not any(row) for row in rows))

    def test_black_pixels_become_ink(self):
        # A 1:1 source into a 4:3 canvas is aspect-fitted and centred; the
        # fitted square must leave ink somewhere while corners stay clear.
        _, _, rows = self.convert(synthetic(4, 4, [(1, 1)]))
        self.assertEqual(rows[0][0], 0)
        self.assertTrue(any(any(row) for row in rows))

    def test_threshold_splits_gray(self):
        gray = Image.new('L', (2, 1), 90)
        _, _, rows = self.convert(gray, width=2, height=1, threshold=128)
        self.assertEqual(rows[0], [1, 1])
        gray = Image.new('L', (2, 1), 200)
        _, _, rows = self.convert(gray, width=2, height=1, threshold=128)
        self.assertEqual(rows[0], [0, 0])

    def test_invert_swaps_black_and_white(self):
        _, _, rows = self.convert(Image.new('L', (1, 1), 0),
                                  width=1, height=1, invert=True)
        self.assertEqual(rows[0], [0])
        _, _, rows = self.convert(Image.new('L', (1, 1), 255),
                                  width=1, height=1, invert=True)
        self.assertEqual(rows[0], [1])

    def test_aspect_fit_letterboxes_to_white(self):
        # A square source into a wide canvas keeps horizontal white margins.
        _, _, rows = self.convert(Image.new('L', (100, 100), 0),
                                  width=100, height=50)
        top = rows[0]
        self.assertEqual(top[0:24], [0] * 24)
        self.assertEqual(top[76:100], [0] * 24)
        self.assertTrue(any(top[25:76]))

    def test_converter_rejects_bad_arguments(self):
        directory = tempfile.TemporaryDirectory()
        source = Path(directory.name) / 'in.png'
        target = Path(directory.name) / 'out.CBM'
        Image.new('L', (8, 8), 255).save(source)
        for width, height in ((0, 8), (8, 0), (321, 8), (8, 201)):
            with self.subTest(width=width, height=height):
                with self.assertRaises(ValueError):
                    convert(source, target, width, height, 128, False)
        directory.cleanup()


if __name__ == '__main__':
    unittest.main()
# SPDX-License-Identifier: GPL-3.0-or-later
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_move_cache_spike import (BITMAP_BYTES, CACHE_BYTES, capture,
                                     needed_bytes, paste, byte_offset)


def pixel(bitmap, x, y):
    return bool(bitmap[byte_offset(x >> 3, y)] & (128 >> (x & 7)))


class WindowMoveCacheSpikeTests(unittest.TestCase):
    def test_default_and_resized_capacity(self):
        self.assertEqual(CACHE_BYTES, 6656)
        self.assertEqual(needed_bytes(168, 104), 2184)
        self.assertEqual(needed_bytes(220, 160), 4480)
        self.assertEqual(needed_bytes(320, 200), 8000)
        self.assertRaises(ValueError, capture, bytes(BITMAP_BYTES), 0, 0, 320, 200)

    def test_randomized_masked_move_preserves_background(self):
        randomizer = random.Random(0x128)
        cases = ((168, 104), (220, 160), (48, 48), (17, 11), (1, 1), (63, 39))
        for width, height in cases:
            for source_align in range(8):
                for target_align in range(8):
                    source_x = source_align + 8
                    target_x = target_align + (320 - width - 8 & ~7)
                    source_y = 200 - height
                    target_y = 0
                    original = bytearray(randomizer.randbytes(BITMAP_BYTES))
                    target = bytearray(randomizer.randbytes(BITMAP_BYTES))
                    expected = bytearray(target)
                    image = capture(original, source_x, source_y, width, height)
                    paste(target, image, target_x, target_y, width, height)
                    for row in range(height):
                        for column in range(width):
                            x, y = target_x + column, target_y + row
                            mask = 128 >> (x & 7)
                            address = byte_offset(x >> 3, y)
                            if pixel(original, source_x + column, source_y + row):
                                expected[address] |= mask
                            else:
                                expected[address] &= ~mask & 255
                    self.assertEqual(target, expected,
                                     (width, height, source_align, target_align))

    def test_right_edge_without_out_of_row_read_or_write(self):
        bitmap = bytearray(BITMAP_BYTES)
        bitmap[byte_offset(39, 199)] = 1
        image = capture(bitmap, 319, 199, 1, 1)
        self.assertEqual(image, b'\x80')
        result = bytearray(BITMAP_BYTES)
        paste(result, image, 319, 199, 1, 1)
        self.assertEqual(result, bitmap)

    def test_capacity_rejects_unsupported_resize_without_touching_bitmap(self):
        bitmap = bytearray(BITMAP_BYTES)
        before = bytes(bitmap)
        with self.assertRaises(ValueError):
            paste(bitmap, bytes(8000), 0, 0, 320, 200)
        self.assertEqual(bitmap, before)


if __name__ == '__main__':
    unittest.main()

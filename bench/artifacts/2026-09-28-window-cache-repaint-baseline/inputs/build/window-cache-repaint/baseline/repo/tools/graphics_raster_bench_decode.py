#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate timer records, independent pixels and dirty maps before comparing."""
import argparse
import hashlib
import json
from pathlib import Path

NAMES = ('short-lines', 'clipped-long-lines', 'aligned-fills', 'clipped-fills')


def reference(case):
    bitmap = bytearray((i * 13 + 7) & 255 for i in range(8000))
    dirty = bytearray(32)
    left, top, right, bottom = (49, 25, 271, 167) if case == 3 else (0, 0, 320, 200)
    def pixel(x, y, color):
        if not (left <= x < right and top <= y < bottom):
            return
        offset = (y & 248) * 40 + (x & ~7) + (y & 7)
        mask = 128 >> (x & 7)
        if color == 0:
            bitmap[offset] |= mask
        else:
            bitmap[offset] &= ~mask & 255
        dirty[offset >> 8] = 1
    def line(x, y, xx, yy, color):
        dx, dy = abs(xx - x), -abs(yy - y)
        sx, sy = (1 if x < xx else -1), (1 if y < yy else -1)
        error = dx + dy
        while True:
            pixel(x, y, color)
            if x == xx and y == yy:
                break
            twice = error * 2
            if twice >= dy:
                error += dy
                x += sx
            if twice <= dx:
                error += dx
                y += sy
    if case == 0:
        for n in range(96):
            x, y = n % 24 * 11 + 10, n % 16 * 9 + 10
            line(x, y, x + 17, y + 11, n & 1)
    elif case == 1:
        for n in range(24):
            line(-20, n * 7, 340, 190 - n * 6, n & 1)
    elif case in (2, 3):
        for n in range(24):
            x, y = (32, 40) if case == 2 else (-10 + n * 7, 8 + n * 3)
            for yy in range(y, y + (80 if case == 2 else 90)):
                for xx in range(x, x + 160):
                    pixel(xx, yy, n & 1)
    else:
        raise ValueError('unknown workload')
    return bytes(bitmap + dirty)


def decode(data, variant, case):
    if len(data) != 8096 or data[:8] != b'RAST\x01\x02' + bytes((variant, case)):
        raise ValueError('invalid or incomplete raster record')
    if any(data[12:64]):
        raise ValueError('reserved result bytes are nonzero')
    elapsed = int.from_bytes(data[8:12], 'little')
    if not elapsed:
        raise ValueError('zero elapsed timer count')
    if data[64:] != reference(case):
        raise ValueError('bitmap or dirty map differs from independent reference')
    return elapsed


def compare(directory):
    report = {'unit': 'cascaded CIA1 timer counts at 1 MHz; includes fixed call/stop overhead',
              'display': 'disabled; IRQs masked; no bitmap commit or compositor', 'cases': []}
    for case, name in enumerate(NAMES):
        row = {'name': name}
        pixels = []
        for engine in ('1986', 'vice'):
            counts = []
            for variant, label in enumerate(('baseline', 'static-scratch')):
                data = (directory / f'{engine}-{label}-{case}.bin').read_bytes()
                counts.append(decode(data, variant, case))
                pixels.append(data[64:])
            row[engine] = {'baseline': counts[0], 'static_scratch': counts[1],
                           'reduction_percent': round(100 * (1 - counts[1] / counts[0]), 3)}
        if len(set(pixels)) != 1:
            raise ValueError('engine or variant pixel mismatch')
        row['pixels_dirty_sha256'] = hashlib.sha256(pixels[0]).hexdigest()
        report['cases'].append(row)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(compare(args.directory), indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()

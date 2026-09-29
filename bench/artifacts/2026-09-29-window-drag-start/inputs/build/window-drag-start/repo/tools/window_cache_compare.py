#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare qualified cache primitives, never claim end-to-end GUI speed."""
import argparse
import json
from pathlib import Path
from window_cache_bench import decode, decode_matrix

ROOT = Path(__file__).resolve().parents[1]


def compare(baseline, assembly):
    old, new = decode(baseline / 'raw'), decode(assembly / 'raw')
    report = {'qualification': 'isolated 1 MHz, display-off, IRQ-masked primitive counts; not GUI latency',
              'cases': []}
    for before, after in zip(old['cases'], new['cases']):
        if (before['alignment'] != after['alignment'] or
                before['pixels_dirty_sha256'] != after['pixels_dirty_sha256']):
            raise ValueError('cannot compare mismatched geometry/pixels')
        row = {'case': before['alignment']}
        for engine in ('1986', 'vice'):
            row[engine] = {}
            for phase in ('capture', 'paste', 'total'):
                a, b = before[engine][phase + '_ticks'], after[engine][phase + '_ticks']
                row[engine][phase] = {'baseline_ticks': a, 'assembly_ticks': b,
                                     'speedup': round(a / b, 4),
                                     'reduction_percent': round((a - b) * 100 / a, 4)}
        report['cases'].append(row)
    report['matrix'] = {engine: decode_matrix((assembly / 'raw' / f'{engine}-matrix.bin').read_bytes())
                        for engine in ('1986', 'vice')}
    for engine in ('1986',):
        a = json.loads((baseline / f'{engine}-provenance.json').read_text())
        b = json.loads((assembly / f'{engine}-provenance.json').read_text())
        report[engine + '_same_inputs'] = a['input_sha256'] == b['input_sha256']
    report['vice_same_flatpak'] = ((baseline / 'VICE-flatpak.txt').read_text() ==
                                  (assembly / 'VICE-flatpak.txt').read_text())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path,
                        default=ROOT / 'bench/results/2026-09-28-window-cache-transfer')
    parser.add_argument('--assembly', type=Path,
                        default=ROOT / 'bench/results/2026-09-28-window-cache-asm')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    content = json.dumps(compare(args.baseline, args.assembly), indent=2) + '\n'
    if args.output is not None: args.output.write_text(content)
    else: print(content, end='')


if __name__ == '__main__':
    main()

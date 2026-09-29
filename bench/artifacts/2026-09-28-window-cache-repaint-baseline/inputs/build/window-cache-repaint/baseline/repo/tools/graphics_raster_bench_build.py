#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build standalone baseline/candidate PRGs; never replace production outputs."""
import argparse
import re
import subprocess
from pathlib import Path
from graphics_raster_audit import ROOT, REFERENCE_SOURCE, automatic_locals_variant, static_scratch_variant


def function(source, name):
    match = re.search(r'^(?:static )?(?:void|unsigned int) ' + name + r'\([^{}]*\)\n\{', source, re.M)
    if not match:
        raise ValueError(f'missing raster function {name}')
    end = match.end()
    depth = 1
    while depth and end < len(source):
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    if depth:
        raise ValueError('unterminated raster function')
    return source[match.start():end] + '\n'


def raster_unit(source):
    if source.count('static void increment_counter(') != 1:
        raise ValueError('unexpected raster prefix boundary')
    prefix = source.split('static void increment_counter(', 1)[0]
    return prefix + '\n'.join(function(source, name) for name in
                              ('unsigned_magnitude', 'udeks_vic_bitmap_line', 'udeks_vic_bitmap_fill'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=ROOT / 'build/graphics-raster-bench')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    source = REFERENCE_SOURCE.read_text()
    launcher = args.work / 'launcher.o'
    subprocess.run(['ca65', '--cpu', '6502', '-o', str(launcher),
                    str(ROOT / 'bench/graphics-raster/launcher.s')], check=True)
    for variant, text in enumerate((automatic_locals_variant(source), static_scratch_variant(source))):
        name = ('baseline', 'static-scratch')[variant]
        unit = args.work / (name + '.c')
        unit.write_text(raster_unit(text))
        obj = unit.with_suffix('.o')
        subprocess.run(['cl65', '-t', 'none', '--cpu', '6502', '-Oirs', '--standard', 'c99',
                        '-I', str(ROOT / 'include'), '-c', '-o', str(obj), str(unit)], check=True)
        for case in range(4):
            stem = args.work / f'{name}-{case}'
            workload = args.work / f'workload-{variant}-{case}.o'
            subprocess.run(['cl65', '-t', 'none', '--cpu', '6502', '-Oirs', '--standard', 'c99',
                            '-I', str(ROOT / 'include'), '-D', f'VARIANT={variant}', '-D', f'CASE={case}',
                            '-c', '-o', str(workload),
                            str(ROOT / 'bench/graphics-raster/workload.c')], check=True)
            subprocess.run(['cl65', '-t', 'none', '--cpu', '6502',
                            '-C', str(ROOT / 'cfg/8502-raster-bench.cfg'), '-m', str(stem.with_suffix('.map')),
                            '-o', str(stem.with_suffix('.bin')), str(launcher), str(obj), str(workload)], check=True)
            stem.with_suffix('.prg').write_bytes(b'\x00\x20' + stem.with_suffix('.bin').read_bytes())
    print(f'built eight standalone 1-MHz raster probes in {args.work}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile an isolated raster scratch-storage experiment, never the kernel.

Object-size savings are not linked savings or a speed benchmark. Generated
variants live only in the caller's build directory; production stays intact.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = ('udeks_vic_bitmap_line', 'udeks_vic_bitmap_fill')


def static_scratch_variant(source):
    for function in FUNCTIONS:
        pattern = (r'(void ' + function + r'\([^{}]*\)\n\{\n)'
                   r'((?:    (?:int|unsigned int|unsigned char) \w+;\n)+)')
        def replace(match):
            return match[1] + match[2].replace('    ', '    static ')
        source, count = re.subn(pattern, replace, source)
        if count != 1:
            raise ValueError(f'{function}: expected exactly one local declaration block')
    return source


def static_arguments_variant(source):
    source = static_scratch_variant(source)
    for function in FUNCTIONS:
        pattern = (r'void ' + function + r'\(([^{}]*)\)\n\{\n'
                   r'((?:    static (?:int|unsigned int|unsigned char) \w+;\n)+)')
        def replace(match):
            parameters = [item.strip() for item in match[1].split(',')]
            declarations, assignments, inputs = [], [], []
            for parameter in parameters:
                kind, name = parameter.rsplit(' ', 1)
                if kind not in ('int', 'unsigned char') or not name.isidentifier():
                    raise ValueError('unexpected raster parameter')
                inputs.append(f'{kind} input_{name}')
                declarations.append(f'    static {parameter};\n')
                assignments.append(f'    {name} = input_{name};\n')
            return ('void ' + function + '(' + ', '.join(inputs) + ')\n{\n' +
                    ''.join(declarations) + match[2] + '\n' + ''.join(assignments))
        source, count = re.subn(pattern, replace, source)
        if count != 1:
            raise ValueError(f'{function}: expected exactly one signature/declaration block')
    return source


def segment_sizes(dump):
    sizes = {}
    for name, size in re.findall(r'Name:\s*"([^"]+)"\s+Flags:\s*\d+\s+Size:\s*(\d+)', dump):
        if name in sizes:
            raise ValueError(f'duplicate segment {name}')
        sizes[name] = int(size)
    if not {'CODE', 'BSS', 'VICSHADOW'} <= sizes.keys():
        raise ValueError('missing required object segments')
    return sizes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=ROOT / 'build/graphics-raster-audit')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    original = (ROOT / 'src/services/display/vic_graphics.c').read_text()
    report = {'source_sha256': hashlib.sha256(original.encode()).hexdigest(),
              'cc65': subprocess.check_output(['cc65', '--version'], stderr=subprocess.STDOUT,
                                               text=True).strip(),
              'qualification': 'compile-only; no resident link or runtime speed claim'}
    variants = (('baseline', original), ('static-scratch', static_scratch_variant(original)),
                ('static-arguments', static_arguments_variant(original)))
    for name, source in variants:
        path = args.work / name
        path.with_suffix('.c').write_text(source)
        subprocess.run(['cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Oirs',
                        '-I', str(ROOT / 'include'), '-o', str(path.with_suffix('.s')),
                        str(path.with_suffix('.c'))], check=True)
        subprocess.run(['ca65', '--cpu', '6502', '-o', str(path.with_suffix('.o')),
                        str(path.with_suffix('.s'))], check=True)
        dump = subprocess.check_output(['od65', '--dump-segments', str(path.with_suffix('.o'))], text=True)
        path.with_suffix('.segments.txt').write_text(dump)
        report[name] = segment_sizes(dump)
    report['code_saved'] = report['baseline']['CODE'] - report['static-scratch']['CODE']
    report['bss_added'] = report['static-scratch']['BSS'] - report['baseline']['BSS']
    report['net_object_bytes_saved'] = report['code_saved'] - report['bss_added']
    report['arguments_code_saved'] = report['baseline']['CODE'] - report['static-arguments']['CODE']
    report['arguments_bss_added'] = report['static-arguments']['BSS'] - report['baseline']['BSS']
    report['arguments_net_object_bytes_saved'] = report['arguments_code_saved'] - report['arguments_bss_added']
    text = json.dumps(report, indent=2) + '\n'
    (args.work / 'report.json').write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()

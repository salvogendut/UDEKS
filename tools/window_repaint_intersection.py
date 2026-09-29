#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private cc65/full-link sizing of still-used manager clipping; no boot image."""
import json
import hashlib
from pathlib import Path
import subprocess

from graphics_span_bench import object_sizes
from graphics_raster_link_audit import link_command, segments
from window_repaint_compact import isolated_config, library_inventory

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'bench/artifacts/2026-09-29-repaint-geometry/build/replacement.c'
WORK = ROOT / 'build/window-repaint-intersection'
DECLARATIONS = '''    unsigned int left;
    unsigned char top;
    unsigned int right;
    unsigned char bottom;'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
REUSE_BODY = '''static unsigned char set_damage_intersection(
    unsigned int x, unsigned char y,
    unsigned int width, unsigned char height)
{
    unsigned int left;
    unsigned char top;

    left = x;
    if (left < damage_left) left = damage_left;
    top = y;
    if (top < damage_top) top = damage_top;
    width += x;
    if (width > damage_right) width = damage_right;
    height = (unsigned char)(height + y);
    if (height > damage_bottom) height = damage_bottom;
    if (left >= width || top >= height) return 0;
    udeks_vic_bitmap_set_clip(left, top, width - left, height - top);
    CACHE_PARTIAL_FIRST = top - y;
    CACHE_PARTIAL_END = height - y;
    CACHE_PARTIAL_WIDTH = width - x;
    return 1;
}'''


def variant(source, selected):
    if source.count(DECLARATIONS) != 1:
        raise ValueError('intersection local declaration seam changed')
    return source.replace(DECLARATIONS, '\n'.join(
        '    ' + ('register ' if name in selected else '') + typ + ' ' + name + ';'
        for typ, name in (('unsigned int', 'left'), ('unsigned char', 'top'),
                          ('unsigned int', 'right'), ('unsigned char', 'bottom'))))


def replace_function(source, body):
    marker = 'static unsigned char set_damage_intersection('
    if source.count(marker) != 1:
        raise ValueError('intersection body seam changed')
    start = source.index(marker)
    end = source.index('\n}', start) + 2
    return source[:start] + body + source[end:]


def compile_variant(name, source):
    stem = WORK / name
    stem.with_suffix('.c').write_text(source)
    subprocess.run(['cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99',
                    '-Oirs', '-I', str(ROOT / 'include'),
                    '-I', str(ROOT / 'bench/window-repaint-scenes'),
                    '-o', str(stem.with_suffix('.s')),
                    str(stem.with_suffix('.c'))], check=True)
    subprocess.run(['ca65', '-o', str(stem.with_suffix('.o')),
                    str(stem.with_suffix('.s'))], check=True)
    return object_sizes(stem.with_suffix('.o'))


def full_links():
    links = {}
    for name, cfg, target in (
        ('normal', '8502-bootstrap.cfg', 'build/8502/udeks-8502.bin'),
        ('panic', '8502-panic-probe.cfg', 'build/8502/udeks-8502-panic-probe.bin'),
    ):
        dry = subprocess.check_output(['make', '-Bn', target], cwd=ROOT, text=True)
        command = link_command(dry.replace('cfg/8502-panic-probe.cfg',
                                           'cfg/8502-bootstrap.cfg'))
        directory = WORK / name
        directory.mkdir(exist_ok=True)
        config = directory / 'isolated.cfg'
        config.write_text(isolated_config((ROOT / 'cfg' / cfg).read_text(), directory))
        seen = {}
        inventory = {}
        for variant in ('baseline', 'reuse_registers'):
            link = list(command)
            link[link.index('-C') + 1] = str(config)
            link[link.index('-m') + 1] = str(directory / (variant + '.map'))
            link[link.index('-o') + 1] = str(directory / (variant + '.bin'))
            link[link.index('build/8502/window_manager.o')] = str(WORK / (variant + '.o'))
            link += [str(ROOT / 'build/window-repaint-callers' / (n + '.o')) for n in
                     ('damage', 'receipt', 'binding', 'control')]
            link += [str(ROOT / 'build/window-repaint-admission' / (n + '.o')) for n in
                     ('admission_bank0', 'transaction_damage')]
            subprocess.run(link, cwd=ROOT, check=True)
            table = (directory / (variant + '.map')).read_text()
            seen[variant] = segments(table)
            inventory[variant] = library_inventory(table)
        prior = segments((ROOT / 'build/window-repaint-admission' / name /
                          'kernel-bank0.map').read_text())
        old, new = seen['baseline'], seen['reuse_registers']
        if old != prior:
            raise ValueError('intersection baseline does not replay admission link: ' + name)
        if any(old[s] != new[s] for s in old if s not in
               ('CODE', 'RODATA', 'DATA', 'BSS', 'VICSHADOW')):
            raise ValueError('intersection variant moved fixed state/range: ' + name)
        if any(old[s]['size'] != new[s]['size'] for s in
               ('RODATA', 'DATA', 'BSS', 'VICSHADOW')) or inventory['baseline'] != inventory['reuse_registers']:
            raise ValueError('intersection variant changed data/helper closure: ' + name)
        links[name] = {'code_saved': old['CODE']['size'] - new['CODE']['size'],
                       'shadow_start_delta': new['VICSHADOW']['start'] - old['VICSHADOW']['start'],
                       'state_unchanged': True,
                       'baseline_map_sha256': digest(directory / 'baseline.map'),
                       'candidate_map_sha256': digest(directory / 'reuse_registers.map')}
    if {value['code_saved'] for value in links.values()} != {23}:
        raise ValueError('intersection savings changed')
    return links


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    source = SOURCE.read_text().replace(
        '#include "../window-repaint-scenes/packet.h"', '#include "packet.h"')
    results = {'baseline': compile_variant('baseline', source)}
    for name, selected in (('x_registers', {'left', 'right'}),
                           ('y_registers', {'top', 'bottom'}),
                           ('all_registers', {'left', 'top', 'right', 'bottom'})):
        results[name] = compile_variant(name, variant(source, selected))
    reuse = replace_function(source, REUSE_BODY)
    results['reuse_params'] = compile_variant('reuse_params', reuse)
    results['reuse_registers'] = compile_variant('reuse_registers', reuse.replace(
        '    unsigned int left;\n    unsigned char top;',
        '    register unsigned int left;\n    register unsigned char top;'))
    report = {'objects': {name: {'CODE': sizes['CODE'], 'delta': sizes['CODE'] -
              results['baseline']['CODE']} for name, sizes in results.items()},
              'links': full_links(),
              'scope': 'UNBOOTABLE private clipping optimization only; no caller/provider/delivery migration',
              'inputs_sha256': {str(path.relative_to(ROOT)): digest(path) for path in
                                (SOURCE, Path(__file__),
                                 ROOT / 'build/window-repaint-admission/report.json',
                                 ROOT / 'build/window-repaint-callers/budget.json')}}
    (WORK / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

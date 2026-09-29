#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile-only lane/row-backend sizing. No disk delivery or resident link."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from graphics_raster_bench_build import function
from graphics_cache_placement import listing_functions
from graphics_span_bench import object_sizes
from window_repaint_compact import candidate, imports

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/repaint-lane'
NAME = '2026-09-29-repaint-lane'
SOURCE = ROOT / 'src/services/window/window_manager_cached.c'


def raster_source(source):
    # Strip only the old synchronous decoration functions. Keep all table,
    # drawing, cache and public ABI code for a conservative object comparison.
    for name in ('draw_glyph', 'draw_title', 'draw_chrome'):
        old = function(source, name)
        if source.count(old) != 1:
            raise ValueError('ambiguous chrome seam')
        source = source.replace(old, '')
    # A compile-only compatibility driver keeps all old call sites valid.
    # The normal manager never uses this generated source; its loop remains
    # synchronous and is NOT presented as the new poll integration.
    fragment = (ROOT / 'bench/window-repaint-lane/chrome.inc').read_text()
    wrapper = '''
static void draw_chrome(register const struct udeks_window *window)
{
    unsigned char row;
    for (row = 0; row < window->height; ++row) draw_chrome_row(window, row);
}
'''
    marker = '/* Private C compositor adapter.'
    at = source.index(marker)
    source = source[:at] + fragment + wrapper + '\n' + source[at:]
    return source + '\n' + (ROOT / 'bench/window-repaint-lane/raster.inc').read_text()


def verify_objects(objects):
    lane, compact, raster = (objects[name] for name in ('lane', 'compact', 'raster'))
    if '_lane_raster_step' not in raster['functions'] or '_draw_chrome_row' not in raster['functions']:
        raise ValueError('compiler omitted a measured row/backend entry')
    if lane['segments']['HIGHBSS'] != 18 or compact['segments']['HIGHBSS'] != 76 or raster['segments']['HIGHBSS'] != 76:
        raise ValueError('lane or renderer hidden-state budget changed')
    if any(lane['segments'][name] or raster['segments'][name] for name in ('BSS', 'DATA', 'ZEROPAGE')):
        raise ValueError('lane/row renderer acquired uncharged mutable scratch')


def build(work):
    work = work.resolve()
    if not work.is_relative_to(ROOT / 'build'):
        raise ValueError('compile-only experiment must stay in build/')
    work.mkdir(parents=True, exist_ok=True)
    result = {'scope': 'compile-only lane/row backend; lower bound, not linked closure or poll integration', 'objects': {}}
    sources = {'lane': (ROOT / 'src/services/window/repaint_lane.c').read_text(),
               'compact': candidate(SOURCE.read_text()),
               'raster': raster_source(candidate(SOURCE.read_text()))}
    for name, text in sources.items():
        stem = work / name
        stem.with_suffix('.c').write_text(text)
        subprocess.run(['cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Oirs',
            '-I', str(ROOT / 'include'), '-o', str(stem.with_suffix('.s')), str(stem.with_suffix('.c'))], check=True)
        subprocess.run(['ca65', '--cpu', '6502', '-l', str(stem.with_suffix('.lst')),
            '-o', str(stem.with_suffix('.o')), str(stem.with_suffix('.s'))], check=True)
        result['objects'][name] = {'segments': object_sizes(stem.with_suffix('.o')),
            'functions': listing_functions(stem.with_suffix('.lst').read_text()), 'imports': imports(stem.with_suffix('.o'))}
    subprocess.run(['cl65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Oirs', '-I', str(ROOT / 'include'),
        '-c', '-o', str(work / 'layout.o'), str(ROOT / 'bench/window-repaint-lane/layout.c')], check=True)
    subprocess.run(['ld65', '-C', str(ROOT / 'cfg/8502-repaint-layout.cfg'),
        '-o', str(work / 'layout.bin'), str(work / 'layout.o')], check=True)
    layout = (work / 'layout.bin').read_bytes()
    if layout != bytes([18, 6, 12, 9]):
        raise ValueError('target lane/work/scene layouts changed')
    lane, compact, raster = (result['objects'][name] for name in ('lane', 'compact', 'raster'))
    verify_objects(result['objects'])
    result['layout'] = dict(zip(('lane', 'ticket', 'work', 'scene_view'), layout))
    result['state_replacement'] = {'compact_manager': 76, 'old_damage_removed': 6, 'lane_added': 18,
        'total': 88, 'accepted_manager_total': 88,
        'qualification': 'requires real poll/interlock replacement; old damage globals are still present in sizing object'}
    result['code'] = {'lane': lane['segments']['CODE'], 'row_adapter_delta': raster['segments']['CODE'] - compact['segments']['CODE'],
        'scope': 'objects only; synchronous compatibility loop and uncalled raster entry still included'}
    functions = compact['functions']
    old = sum(functions[name]['size'] for name in ('_draw_glyph', '_draw_title', '_draw_chrome',
                                                  '_paint_window_damage', '_compose_damage'))
    new = lane['segments']['CODE'] + sum(raster['functions'][name]['size'] for name in ('_draw_chrome_row', '_lane_raster_step'))
    result['code']['optimistic_shortfall'] = new - old - 137
    result['code']['shortfall_scope'] = ('lower bound only: grants all five old function bodies plus 137 reserve bytes; '
        'excludes new call sites, helper closure, legacy/cache adapters and admission/teardown interlocks')
    result['toolchain'] = {name: subprocess.check_output([name, '--version'], stderr=subprocess.STDOUT,
        text=True).strip() for name in ('cc65', 'ca65', 'ld65', 'cl65')}
    inputs = [SOURCE, ROOT / 'src/services/window/repaint_lane.c', ROOT / 'src/services/window/repaint_policy.c',
        ROOT / 'include/udeks/repaint_lane.h', ROOT / 'include/udeks/window_repaint.h', ROOT / 'include/udeks/window.h',
        ROOT / 'include/udeks/vic_graphics.h', ROOT / 'include/udeks/memory.h', ROOT / 'include/udeks/pointer.h',
        ROOT / 'include/udeks/window_cache_state.h', ROOT / 'include/udeks/window_cache_command.h',
        ROOT / 'bench/window-repaint-lane/chrome.inc', ROOT / 'bench/window-repaint-lane/raster.inc',
        ROOT / 'bench/window-repaint-lane/layout.c', ROOT / 'bench/window-cache-manager/occlusion-host.inc',
        ROOT / 'tools/repaint_lane_budget.py', ROOT / 'tools/window_repaint_compact.py', ROOT / 'tools/window_cache_manager.py',
        ROOT / 'tools/graphics_raster_bench_build.py', ROOT / 'tools/graphics_span_bench.py',
        ROOT / 'tools/graphics_cache_placement.py', ROOT / 'tools/gen_capability_imports.py',
        ROOT / 'tests/test_repaint_lane.py', ROOT / 'tests/test_repaint_chrome_rows.py',
        ROOT / 'tests/test_repaint_raster.py', ROOT / 'tests/test_repaint_lane_budget.py', ROOT / 'tests/test_window_repaint_policy.py',
        ROOT / 'tests/test_window_cache_manager.py', ROOT / 'tests/test_window_cache_partial_manager.py',
        ROOT / 'Makefile', ROOT / 'mk/toolchain.mk', ROOT / 'cfg/8502-repaint-layout.cfg']
    result['input_sha256'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    result['output_sha256'] = {str(path.relative_to(work)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(work.rglob('*')) if path.is_file() and path.name != 'budget.json'}
    (work / 'budget.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({name: result[name] for name in ('scope', 'layout', 'state_replacement', 'code')}, indent=2))


def preserve(work):
    result = json.loads((work / 'budget.json').read_text())
    artifact, records = ROOT / 'bench/artifacts' / NAME, ROOT / 'bench/results' / NAME
    if artifact.exists() or records.exists():
        raise ValueError('refusing to overwrite lane evidence')
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    for name, expected in result['input_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('lane input drift: ' + name)
    for name, expected in result['output_sha256'].items():
        if digest(work / name) != expected:
            raise ValueError('lane output drift: ' + name)
    for prefix, files, base in (('inputs', result['input_sha256'], ROOT), ('build', result['output_sha256'], work)):
        for name in files:
            dest = artifact / prefix / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(base / name, dest)
    records.mkdir(parents=True)
    shutil.copy2(work / 'budget.json', records / 'budget.json')
    for directory in (artifact, records):
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.relative_to(directory)}\n'
            for path in sorted(directory.rglob('*')) if path.is_file()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=WORK)
    parser.add_argument('--preserve', action='store_true')
    args = parser.parse_args()
    build(args.work)
    if args.preserve:
        preserve(args.work)

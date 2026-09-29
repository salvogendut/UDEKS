#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Host-tested private frontend and UNBOOTABLE full-link budget; no OS disk."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import window_repaint_raster as raster
from graphics_cache_placement import listing_functions
from graphics_span_bench import object_sizes
from window_repaint_compact import imports

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/window-repaint-frontend'
NAME = '2026-09-29-repaint-frontend'
PRIOR = ROOT / 'bench/results/2026-09-29-repaint-raster/budget.json'
ART = ROOT / 'bench/artifacts/2026-09-29-repaint-raster'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_budget(report, prior):
    obj = report['object']
    if not {'_repaint_frontend_control', '_repaint_frontend_poll', '_repaint_frontend_allowed'} <= set(obj['functions']):
        raise ValueError('compiler omitted a charged frontend entry')
    if obj['segments']['HIGHBSS'] != 88 or any(obj['segments'].get(n, 0) for n in ('BSS', 'DATA', 'ZEROPAGE')):
        raise ValueError('frontend acquired hidden persistent state')
    for link in report['links'].values():
        if link['code_growth'] != (obj['segments']['CODE'] - 7762 + 127 + 84 + link['library_delta']):
            raise ValueError('full link and object/helper charges disagree')
    deltas = {v['library_delta'] for v in report['links'].values()}
    if len(deltas) != 1:
        raise ValueError('normal/panic helper closure differs')
    b = report['budget']
    if b['replacement_budget'] != 2113:
        raise ValueError('replacement allowance changed')
    if b['frontend_delta'] != obj['segments']['CODE'] - prior['objects']['replacement']['segments']['CODE']:
        raise ValueError('frontend delta changed')
    if b['new_helper_closure'] != deltas.pop():
        raise ValueError('helper charge missing')
    expected = prior['component_budget']['charged'] + b['frontend_delta'] + b['new_helper_closure'] - prior['component_budget']['new_helper_closure']
    if b['charged'] != expected or b['shortfall'] != expected - 2113:
        raise ValueError('lower-bound accounting changed')


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    for directory in (ART, PRIOR.parent):
        for line in (directory / 'SHA256SUMS').read_text().splitlines():
            sha, name = line.split('  ', 1)
            if digest(directory / name) != sha:
                raise ValueError('prior qualified evidence drift: ' + name)
    prior = json.loads(PRIOR.read_text())
    source = raster.compact_source(raster.SOURCE.read_text()) + '\n' + (ROOT / 'bench/window-repaint-frontend/frontend.inc').read_text()
    stem = WORK / 'replacement'
    stem.with_suffix('.c').write_text(source)
    subprocess.run(['cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Oirs',
        '-I', str(ROOT / 'include'), '-I', str(ROOT / 'bench/window-repaint-frontend'),
        '-o', str(stem.with_suffix('.s')), str(stem.with_suffix('.c'))], check=True)
    subprocess.run(['ca65', '-l', str(stem.with_suffix('.lst')), '-o', str(stem.with_suffix('.o')),
        str(stem.with_suffix('.s'))], check=True)
    obj = {'segments': object_sizes(stem.with_suffix('.o')),
        'functions': listing_functions(stem.with_suffix('.lst').read_text()), 'imports': imports(stem.with_suffix('.o'))}
    for name in ('receipt.o', 'binding.o'):
        shutil.copy2(ART / 'build' / name, WORK / name)
    old_work = raster.WORK
    try:
        raster.WORK = WORK
        links = raster.whole_links()
    finally:
        raster.WORK = old_work
    delta = obj['segments']['CODE'] - prior['objects']['replacement']['segments']['CODE']
    closure = links['normal']['library_delta']
    charged = prior['component_budget']['charged'] + delta + closure - prior['component_budget']['new_helper_closure']
    report = {'scope': 'UNBOOTABLE isolated host-tested frontend sizing; not wired to real manager poll/lifecycle, no admission/NMI/provider qualification',
        'object': obj, 'links': links, 'budget': {'frontend_delta': delta,
        'new_helper_closure': closure, 'charged': charged, 'replacement_budget': 2113, 'shortfall': charged - 2113,
        'scope': 'component lower bound; excludes call-site migration, admission/delivery, busy/teardown and real providers'},
        'possible_retirements': {n:prior['objects']['compact']['functions'][n]['size'] for n in (
            '_damage_set', '_damage_add', '_set_damage_intersection', '_cache_paint_image')},
        'retirement_scope': 'NOT granted as free code: legacy cache/drag/callback paths still use these functions',
        'state': 'manager76 + row scratch12 = 88; no frontend globals; future admission/paint lease flag/caller costs uncharged',
        'toolchain': {n:subprocess.check_output([n,'--version'],stderr=subprocess.STDOUT,text=True).strip()
            for n in ('cc65','ca65','ld65','cl65')}}
    verify_budget(report, prior)
    paths = [Path(__file__), ROOT / 'bench/window-repaint-frontend/frontend.inc',
        ROOT / 'tests/test_window_repaint_frontend.py', ROOT / 'tests/test_window_repaint_frontend_budget.py',
        ROOT / 'tools/window_repaint_raster.py', ROOT / 'tools/window_repaint_compact.py',
        ROOT / 'tools/repaint_lane_budget.py', ROOT / 'tools/graphics_cache_placement.py',
        ROOT / 'tools/graphics_span_bench.py', ROOT / 'tools/graphics_raster_link_audit.py',
        ROOT / 'tools/placement_audit.py', ROOT / 'tools/gen_capability_imports.py',
        ROOT / 'tools/window_cache_manager.py', ROOT / 'Makefile', ROOT / 'mk/toolchain.mk',
        ROOT / 'cfg/8502-bootstrap.cfg', ROOT / 'cfg/8502-panic-probe.cfg', PRIOR,
        ART / 'SHA256SUMS', PRIOR.parent / 'SHA256SUMS', ART / 'build/receipt.o', ART / 'build/binding.o',
        ROOT / 'src/services/window/window_manager_cached.c', ROOT / 'src/services/window/repaint_lane.c',
        ROOT / 'src/services/window/move_cache_state.c', ROOT / 'bench/window-repaint-bank/dispatch.c',
        ROOT / 'bench/window-repaint-bank/packet.h', ROOT / 'bench/window-repaint-raster/receipt.c',
        ROOT / 'bench/window-repaint-raster/chrome.inc', ROOT / 'bench/window-repaint-raster/raster.inc',
        ROOT / 'bench/window-repaint-lane/chrome.inc', ROOT / 'bench/window-repaint-lane/raster.inc',
        ROOT / 'bench/window-cache-manager/occlusion-host.inc',
        ROOT / 'tests/test_window_cache_manager.py', ROOT / 'tests/test_window_cache_partial_manager.py']
    paths += list((ROOT / 'include/udeks').glob('*.h'))
    report['input_sha256'] = {str(p.relative_to(ROOT)):digest(p) for p in paths}
    for link in links.values():
        report['input_sha256'].update(link['input_sha256'])
    report['output_sha256'] = {str(p.relative_to(WORK)):digest(p) for p in sorted(WORK.rglob('*'))
        if p.is_file() and p.name != 'budget.json'}
    (WORK / 'budget.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({n:report[n] for n in ('scope', 'budget', 'possible_retirements', 'retirement_scope', 'state')}, indent=2))


def preserve():
    report = json.loads((WORK / 'budget.json').read_text())
    verify_budget(report, json.loads(PRIOR.read_text()))
    art = ROOT / 'bench/artifacts' / NAME
    result = ROOT / 'bench/results' / NAME
    if art.exists() or result.exists():
        raise ValueError('refusing to overwrite evidence')
    for base, files in ((ROOT, report['input_sha256']), (WORK, report['output_sha256'])):
        for n, sha in files.items():
            if digest(base / n) != sha:
                raise ValueError('qualification drift: ' + n)
    for prefix, files, base in (('inputs', report['input_sha256'], ROOT), ('build', report['output_sha256'], WORK)):
        for n in files:
            dest = art / prefix / n
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(base / n, dest)
    result.mkdir(parents=True)
    shutil.copy2(WORK / 'budget.json', result / 'budget.json')
    for directory in (art, result):
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n'
            for p in sorted(directory.rglob('*')) if p.is_file()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preserve', action='store_true')
    args = parser.parse_args()
    build()
    if args.preserve:
        preserve()

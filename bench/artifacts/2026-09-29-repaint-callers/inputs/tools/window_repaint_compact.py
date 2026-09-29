#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private manager state-reclaim experiment, never a disk or import provider.

Rank zero denotes a free slot. Only bitmap surfaces are admitted by create;
owner is accepted by the public API but has no internal reader. Neither the
public API nor the diagnostic record changes. Measure both whole-link variants
in isolation: ALL split outputs must stay below the experimental directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from gen_capability_imports import canonicalize
from graphics_cache_placement import listing_functions
from graphics_raster_link_audit import link_command, segments
from graphics_span_bench import object_sizes
from placement_audit import parse_map
from window_cache_manager import replace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/services/window/window_manager_cached.c'
WORK = ROOT / 'build/window-repaint-compact'
NAME = '2026-09-29-repaint-compact'


def candidate(source):
    # Fail closed if a new reader appears; never discard a newly meaningful
    # owner/surface field just because today's implementation does not use it.
    if len(re.findall(r'(?:->|\.)owner\b', source)) != 1 or len(re.findall(r'(?:->|\.)surface\b', source)) != 2:
        raise ValueError('owner/surface lifetime changed; review state reclaim')
    for field in ('active', 'owner', 'surface'):
        source = replace(source, f'    unsigned char {field};\n', '')
    for line in ('    window->active = 1;\n', '    window->owner = owner;\n',
                 '    window->surface = surface;\n'):
        source = replace(source, line, '')
    source = replace(source, '''        (window->flags & UDEKS_WINDOW_FLAG_VISIBLE) == 0 ||
        window->surface != UDEKS_WINDOW_SURFACE_BITMAP)''',
        '''        (window->flags & UDEKS_WINDOW_FLAG_VISIBLE) == 0)''')
    source = source.replace('.active', '.z').replace('->active', '->z')
    # On destruction old_z is already saved before the new free-slot write.
    if 'old_z = window->z;' not in source or 'window->z = 0;' not in source:
        raise ValueError('destroy rank retirement seam changed')
    # Collapse now-redundant rank/live checks without changing sparse-slot scans.
    source = replace(source, 'windows[index].z != 0 && windows[index].z == rank',
                     'windows[index].z == rank')
    # Keep the live check in top_window: when active_count == 0, every FREE
    # rank is also zero. Dropping that check would publish a phantom focus.
    source = source.replace('windows[index].z != 0 && windows[index].z > old_z',
                            'windows[index].z > old_z')
    source = replace(source, '    if (width < 16u || height <= UDEKS_WINDOW_TITLE_HEIGHT + 4u ||',
                     '    (void)owner; /* Public parameter retained; no current internal reader. */\n'
                     '    if (width < 16u || height <= UDEKS_WINDOW_TITLE_HEIGHT + 4u ||')
    return source


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def imports(path):
    dump = subprocess.check_output(['od65', '--dump-imports', str(path)], text=True)
    path.with_suffix('.imports.txt').write_text(dump)
    return canonicalize([(name, size.lower()) for size, name in re.findall(
        r'Address size:\s+0x([0-9A-Fa-f]+).*?Name:\s*"([^"]+)"', dump, re.S)])


def library_inventory(map_text):
    modules, _ = parse_map(map_text)
    libraries = {name: sizes for name, sizes in modules.items()
                 if re.search(r'(?:^|/)none\.lib\([^)]+\)$', name)}
    if not libraries:
        raise ValueError('missing linked library inventory')
    return libraries


def isolated_config(text, directory):
    def output(match):
        target = directory / Path(match[1]).name
        return 'file = "' + str(target) + '"'
    result = re.sub(r'file = "(build/[^"\n]+)"', output, text)
    # %O is supplied by -o; empty file names are non-file-backed allocations.
    for filename in re.findall(r'file\s*=\s*"([^"]*)"', result):
        if filename and not Path(filename).is_relative_to(directory):
            raise ValueError('split linker output escaped private experiment')
    return result


def build(work):
    work = work.resolve()
    if not work.is_relative_to(ROOT / 'build'):
        raise ValueError('experiment must stay in repository build/')
    work.mkdir(parents=True, exist_ok=True)
    report = {'scope': 'UNBOOTABLE state-reclaim budget links; no delivery/import bridge regeneration',
              'variants': {}, 'links': {}}
    for label, source in (('baseline', SOURCE.read_text()), ('compact', candidate(SOURCE.read_text()))):
        stem = work / label
        stem.with_suffix('.c').write_text(source)
        subprocess.run(['cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Oirs',
                        '-I', str(ROOT / 'include'), '-o', str(stem.with_suffix('.s')),
                        str(stem.with_suffix('.c'))], check=True)
        subprocess.run(['ca65', '--cpu', '6502', '-l', str(stem.with_suffix('.lst')),
                        '-o', str(stem.with_suffix('.o')), str(stem.with_suffix('.s'))], check=True)
        report['variants'][label] = {'segments': object_sizes(stem.with_suffix('.o')),
            'functions': listing_functions(stem.with_suffix('.lst').read_text()),
            'imports': imports(stem.with_suffix('.o'))}
    base, compact = (report['variants'][label] for label in ('baseline', 'compact'))
    if base['segments']['CODE'] != 7762 or base['segments']['HIGHBSS'] != 88:
        raise ValueError('accepted manager size changed')
    if compact['segments']['HIGHBSS'] != 76:
        raise ValueError('compact state did not reclaim exactly twelve bytes')
    if compact['imports'] != base['imports']:
        raise ValueError('reclaim unexpectedly changed runtime helper closure')
    for normal in (True, False):
        config_name = '8502-bootstrap.cfg' if normal else '8502-panic-probe.cfg'
        target = 'build/8502/udeks-8502.bin' if normal else 'build/8502/udeks-8502-panic-probe.bin'
        dry = subprocess.check_output(['make', '-Bn', target], cwd=ROOT, text=True)
        # Reuse the strict normal parser for the structurally identical panic
        # command; do not execute any other dry-run command.
        command = link_command(dry.replace('cfg/8502-panic-probe.cfg', 'cfg/8502-bootstrap.cfg'))
        input_paths = [ROOT / token for token in command if token.endswith('.o')]
        variant_links, libraries = {}, {}
        for label in ('baseline', 'compact'):
            directory = work / ('normal' if normal else 'panic') / label
            directory.mkdir(parents=True, exist_ok=True)
            cfg = directory / 'isolated.cfg'
            cfg.write_text(isolated_config((ROOT / 'cfg' / config_name).read_text(), directory))
            link = list(command)
            link[link.index('-C') + 1] = str(cfg)
            link[link.index('-m') + 1] = str(directory / 'kernel.map')
            link[link.index('-o') + 1] = str(directory / 'kernel.bin')
            link[link.index('build/8502/window_manager.o')] = str(work / (label + '.o'))
            subprocess.run(link, cwd=ROOT, check=True)
            map_text = (directory / 'kernel.map').read_text()
            variant_links[label] = segments(map_text)
            libraries[label] = library_inventory(map_text)
        # Baseline replay must match the actual built production map first.
        live_map = ROOT / target.replace('.bin', '.map')
        if variant_links['baseline'] != segments(live_map.read_text()):
            raise ValueError('baseline isolated replay differs from real map')
        replay = work / ('normal' if normal else 'panic') / 'baseline/kernel.bin'
        if replay.read_bytes() != (ROOT / target).read_bytes():
            raise ValueError('baseline isolated replay differs from real image')
        old, new = variant_links['baseline'], variant_links['compact']
        high_saved = old['HIGHBSS']['size'] - new['HIGHBSS']['size']
        code_saved = old['CODE']['size'] - new['CODE']['size']
        if high_saved != 12 or code_saved != base['segments']['CODE'] - compact['segments']['CODE']:
            raise ValueError('whole-link savings differ from object measurement')
        fixed = set(old) - {'CODE', 'RODATA', 'DATA', 'BSS', 'VICSHADOW', 'HIGHBSS'}
        if set(old) != set(new) or any(old[name] != new[name] for name in fixed):
            raise ValueError('reclaim altered a fixed segment')
        if old['VICSHADOW']['start'] != 0xA1E0:
            raise ValueError('accepted shadow placement changed')
        if libraries['baseline'] != libraries['compact']:
            raise ValueError('compact experiment changed linked library modules')
        report['links']['normal' if normal else 'panic'] = {
            'baseline': old, 'compact': new, 'code_saved': code_saved, 'highbss_saved': high_saved,
            'library_modules': libraries['compact'], 'command': command,
            'input_sha256': {str(path.relative_to(ROOT)): digest(path)
                for path in input_paths + [live_map, ROOT / target]}}
    library_paths = {name.split('(', 1)[0] for entry in report['links'].values() for name in entry['library_modules']}
    if len(library_paths) != 1:
        raise ValueError('unexpected multiple runtime library providers')
    library = Path(next(iter(library_paths)))
    if not library.is_absolute():
        library = ROOT / library
    shutil.copy2(library, work / 'none.lib')
    report['library_provider'] = {'path': str(library), 'sha256': digest(library), 'archived': 'none.lib'}
    report['state'] = {'window_before': 17, 'window_after': 14, 'slots': 4,
                       'reclaimed': 12, 'reference_job': 22, 'remaining_job_shortfall': 10}
    report['input_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in (
        SOURCE, ROOT / 'tools/window_repaint_compact.py', ROOT / 'tools/window_cache_manager.py',
        ROOT / 'tools/graphics_raster_link_audit.py', ROOT / 'tools/graphics_cache_placement.py',
        ROOT / 'tools/graphics_span_bench.py', ROOT / 'tools/gen_capability_imports.py',
        ROOT / 'tools/placement_audit.py', ROOT / 'tools/graphics_raster_audit.py', ROOT / 'mk/toolchain.mk',
        ROOT / 'cfg/8502-bootstrap.cfg', ROOT / 'cfg/8502-panic-probe.cfg',
        ROOT / 'include/udeks/window.h', ROOT / 'include/udeks/pointer.h',
        ROOT / 'include/udeks/vic_graphics.h', ROOT / 'include/udeks/window_cache_state.h',
        ROOT / 'include/udeks/window_cache_command.h', ROOT / 'Makefile', ROOT / 'tests/test_window_repaint_compact.py',
        ROOT / 'tests/test_window_cache_manager.py', ROOT / 'tests/test_window_cache_partial_manager.py',
        ROOT / 'bench/window-cache-manager/occlusion-host.inc', ROOT / 'src/services/window/move_cache_state.c')}
    report['cc65'] = subprocess.check_output(['cc65', '--version'], stderr=subprocess.STDOUT, text=True).strip()
    report['toolchain'] = {name: subprocess.check_output([name, '--version'], stderr=subprocess.STDOUT,
        text=True).strip() for name in ('cc65', 'ca65', 'ld65', 'cl65')}
    report['output_sha256'] = {str(path.relative_to(work)): digest(path) for path in sorted(work.rglob('*'))
        if path.is_file() and path.name != 'budget.json'}
    (work / 'budget.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'state': report['state'], 'links': {name: {key: entry[key] for key in (
        'code_saved', 'highbss_saved')} for name, entry in report['links'].items()}}, indent=2))


def preserve(work):
    report = json.loads((work / 'budget.json').read_text())
    artifact, result = ROOT / 'bench/artifacts' / NAME, ROOT / 'bench/results' / NAME
    if artifact.exists() or result.exists():
        raise ValueError('refusing to overwrite compact measurement')
    inputs = dict(report['input_sha256'])
    for entry in report['links'].values():
        inputs.update(entry['input_sha256'])
    for name, expected in inputs.items():
        if digest(ROOT / name) != expected:
            raise ValueError('compact input drift: ' + name)
    for name, expected in report['output_sha256'].items():
        if digest(work / name) != expected:
            raise ValueError('compact output drift: ' + name)
    for name in inputs:
        target = artifact / 'inputs' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    for name in report['output_sha256']:
        target = artifact / 'build' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(work / name, target)
    result.mkdir(parents=True)
    shutil.copy2(work / 'budget.json', result / 'budget.json')
    for directory in (artifact, result):
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

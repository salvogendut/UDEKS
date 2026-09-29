#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify actual WINDOW_CACHE=1 normal outputs, never rebuild a private clone."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import window_cache_runtime_probe as live
from build_window_cache import bindings
from gen_capability_imports import map_exports
from graphics_raster_link_audit import segments
from graphics_span_bench import object_sizes
from placement_audit import parse_map
import window_cache_occlusion as occlusion
import window_cache_repaint as repaint

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/window-cache-integration'
NAME = '2026-09-29-window-cache-integration'


def verify_build():
    report = json.loads((WORK / 'report.json').read_text())
    for name, sha in report['inputs_sha256'].items():
        if live.digest(ROOT / name) != sha:
            raise ValueError('integration input drift ' + name)
    for fmt, sha in report['disk_sha256'].items():
        if live.digest(WORK / f'udeks-cache.{fmt}') != sha:
            raise ValueError('integration disk drift ' + fmt)
    return report


def configure():
    live.WORK = WORK
    live.REPO = ROOT
    live.PROOF = WORK / 'delivery'
    live.MODULE_REL = 'build/module.bin'
    live.LOADER_REL = 'build/loader.inc'
    live.verify_build = verify_build
    occlusion.live = live
    repaint.live = live


def prepare():
    if json.loads((ROOT / 'build/8502/window-cache-config.json').read_text()) != {'window_cache': 1}:
        raise ValueError('build WINDOW_CACHE=1 boot panic-probe first')
    configure()
    reference = ROOT / 'bench/artifacts/2026-09-29-window-drag-start/inputs/build/window-drag-start/repo/build/8502'
    measured = {}
    for name in ('udeks-8502', 'udeks-8502-panic-probe'):
        path = ROOT / 'build/8502' / (name + '.map')
        text = path.read_text()
        if segments(text) != segments((reference / path.name).read_text()):
            raise ValueError('frozen segment drift ' + name)
        old, _ = parse_map((reference / path.name).read_text())
        new, _ = parse_map(text)
        if {k: v for k, v in old.items() if k.startswith('none.lib(')} != \
                {k: v for k, v in new.items() if k.startswith('none.lib(')}:
            raise ValueError('runtime helper drift ' + name)
        measured[name] = segments(text)
    manager = object_sizes(ROOT / 'build/8502/window_manager.o')
    transport = object_sizes(ROOT / 'build/8502/cache_transport.o')
    if manager['CODE'] != 7762 or manager['HIGHBSS'] != 88 or \
            transport['CODE'] != 377:
        raise ValueError('charged resident footprint changed')
    module = ROOT / 'build/window-cache/module.bin'
    gateway = ROOT / 'build/window-cache/gateway.bin'
    acceptance, loader = bindings(module.read_bytes(), gateway.read_bytes(),
                                 (ROOT / 'build/window-cache/module.map').read_text())
    if (ROOT / 'build/window-cache/acceptance.inc').read_text() != acceptance or \
            (ROOT / 'build/window-cache/loader.inc').read_text() != loader:
        raise ValueError('stale generated acceptance bindings')
    delivery = live.PROOF / 'build'
    delivery.mkdir(parents=True, exist_ok=True)
    for path in (module, gateway, ROOT / 'build/window-cache/loader.inc'):
        shutil.copy2(path, delivery / path.name)
    for fmt in ('d71', 'd64'):
        shutil.copy2(ROOT / 'build/boot' / f'udeks.{fmt}', WORK / f'udeks-cache.{fmt}')
    paths = [ROOT / 'Makefile', ROOT / 'mk/window-cache.mk',
             ROOT / 'tools/build_window_cache.py', Path(__file__),
             ROOT / 'tools/build_scheduler_overlay.py',
             ROOT / 'src/services/window/window_manager_cached.c',
             ROOT / 'src/8502/cache_transport.s', ROOT / 'src/8502/vic_graphics.s',
             ROOT / 'src/apps/xwave.c']
    paths += list((ROOT / 'src/services/window/cache').glob('*'))
    paths += list((ROOT / 'build/window-cache').glob('*'))
    paths += [ROOT / 'cfg/8502-window-cache.cfg', ROOT / 'cfg/8502-window-cache-gateway.cfg']
    paths += [ROOT / 'build/8502' / (n + suffix)
              for n in measured for suffix in ('.map', '.bin')]
    paths += [ROOT / 'build/boot' / ('udeks.' + fmt) for fmt in ('d71', 'd64')]
    paths += [ROOT / 'build/boot/scheduler-overlay.prg', ROOT / 'build/8502/window-cache-config.json',
              ROOT / 'tools/window_cache_runtime_probe.py', ROOT / 'tools/window_cache_occlusion.py',
              ROOT / 'tools/window_cache_repaint.py', ROOT / 'tools/1986_input_smoke.c',
              ROOT / 'tools/1986_input_smoke_build.py', ROOT / 'tools/vice_capture.py',
              ROOT / 'tools/shadow_boot_probe.py', ROOT / 'tools/nmi_integration_probe.py',
              ROOT / 'bench/window-cache-manager/native.inc']
    symbols = map_exports((ROOT / 'build/8502/udeks-8502.map').read_text())
    report = {'qualification': 'normal WINDOW_CACHE=1 build; hardware-accepted default',
              'manager_sizes': manager, 'transport_sizes': transport, 'segments': measured,
              'symbols': {n: v[0] for n, v in symbols.items() if n.startswith('_cache_')},
              'toolchain': {n: subprocess.check_output([n, '--version'], stderr=subprocess.STDOUT,
                            text=True).strip() for n in ('cc65', 'ca65', 'ld65')},
              'disk_sha256': {fmt: live.digest(WORK / f'udeks-cache.{fmt}') for fmt in ('d71', 'd64')},
              'inputs_sha256': {str(p.relative_to(ROOT)): live.digest(p) for p in paths if p.is_file()}}
    (WORK / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    verify_build()
    print(json.dumps({k: report[k] for k in ('qualification', 'manager_sizes', 'disk_sha256')}, indent=2))


def preserve():
    report = verify_build()
    for engine in ('1986', 'vice'):
        run = json.loads((WORK / f'{engine}-run.json').read_text())
        if run['report_sha256'] != live.digest(WORK / 'report.json') or set(run['results']) != {'d71', 'd64'}:
            raise ValueError('incomplete or stale integration run ' + engine)
        for name, sha in run['raw_sha256'].items():
            if live.digest(WORK / name) != sha:
                raise ValueError('raw evidence drift ' + name)
    native = json.loads((WORK / '1986-run.json').read_text())
    for fmt in ('d71', 'd64'):
        if live.digest(WORK / f'1986-{fmt}.log') != native['results'][fmt]['log_sha256']:
            raise ValueError('native log drift ' + fmt)
    for name, key in (('native', 'runner_sha256'), ('native.c', 'source_sha256')):
        if live.digest(WORK / name) != native[key]:
            raise ValueError('native runner drift ' + name)
    artifact, result = ROOT / 'bench/artifacts' / NAME, ROOT / 'bench/results' / NAME
    if artifact.exists() or result.exists():
        raise ValueError('refusing to overwrite integration evidence')
    for name in report['inputs_sha256']:
        target = artifact / 'inputs' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    shutil.copy2(WORK / 'native', artifact / 'native')
    result.mkdir(parents=True)
    for path in WORK.iterdir():
        if path.is_file() and path.suffix in ('.json', '.bin', '.log', '.c', '.d64', '.d71'):
            shutil.copy2(path, result / path.name)
    for directory in (artifact, result):
        paths = sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(
            f'{live.digest(p)}  {p.relative_to(directory)}\n' for p in paths))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', '1986', 'vice', 'preserve'))
    args = parser.parse_args()
    configure()
    if args.action == 'prepare':
        prepare()
    elif args.action == '1986':
        live.probe_native(occlusion.native_profile)
    elif args.action == 'vice':
        live.probe_vice()
    else:
        preserve()

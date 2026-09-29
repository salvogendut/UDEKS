#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Link the compact transport in isolation; NOT bootable, no compositor hooks."""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from graphics_raster_link_audit import link_command, segments
from graphics_span_bench import object_sizes
from gen_capability_imports import map_exports
from placement_audit import parse_map
from window_cache_controller_delivery import digest

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/window-cache-resident-link'
NAME = '2026-09-28-window-cache-resident-link'
PROOF = ROOT / 'bench/artifacts/2026-09-28-window-cache-compact'
PAD = (('raster_scratch_placement_reserve', 49, 0),
       ('raster_primitives_placement_reserve', 173, 131),
       ('raster_shared_placement_reserve', 280, 0))


def spend_padding(text):
    for label, before, after in PAD:
        old = f'{label}:\n        .res {before}, $ea'
        if text.count(old) != 1:
            raise ValueError('qualified padding changed: '+label)
        text = text.replace(old, f'{label}:\n        .res {after}, $ea')
    return text


def retarget_config(text, directory):
    return re.sub(r'file = "(build/[^"\n]+)"',
        lambda m: 'file = "'+str(directory / Path(m[1]).name)+'"', text)


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    for line in (PROOF / 'SHA256SUMS').read_text().splitlines():
        sha, name = line.split('  ', 1)
        if digest(PROOF / name) != sha:
            raise ValueError('qualified compact proof drift '+name)
    transport = ROOT / 'src/8502/vic_graphics.s'
    (WORK / 'transport.s').write_text(spend_padding(transport.read_text()))
    sources = {'layout.inc': ROOT / 'bench/window-cache-controller/layout.inc',
        'acceptance.inc': PROOF / 'build/acceptance.inc',
        'loader.inc': PROOF / 'build/bench/window-cache-compact/acceptance/loader.inc',
        'validator.bin': PROOF / 'build/validator.bin',
        'raw.s': ROOT / 'bench/window-cache-compact/raw.s'}
    for name, path in sources.items():
        shutil.copy2(path, WORK / name)
    binding = ROOT / 'bench/window-cache-acceptance/binding.s'
    (WORK / 'binding.s').write_text(binding.read_text().replace(
        'build/bench/window-cache-acceptance/validator.bin', str(WORK / 'validator.bin')))
    # Retain the FULL charged diagnostic helper, including its real stores.
    # This is a placement-only link, not a new production fault mechanism.
    driver = PROOF / 'build/driver.s'
    marker = '.segment "CODE"\n.export _cache_copy_fault_probe\n'
    if driver.read_text().count(marker) != 1:
        raise ValueError('diagnostic helper seam changed')
    (WORK / 'helper.s').write_text(marker+driver.read_text().split(marker)[1])
    objects = {}
    for name in ('transport', 'raw', 'binding', 'helper'):
        subprocess.run(['ca65', '--cpu', '6502', '-I', str(WORK), '-I', str(ROOT / 'src/8502'),
            '-o', str(WORK / (name+'.o')), str(WORK / (name+'.s'))], check=True)
        objects[name] = object_sizes(WORK / (name+'.o'))
    charged = sum(objects[n]['CODE'] for n in ('raw', 'binding', 'helper'))
    if charged != 371 or any(objects[n].get(s, 0) for n in ('raw', 'binding', 'helper')
            for s in ('BSS', 'DATA', 'ZEROPAGE', 'RODATA')):
        raise ValueError('charged transport closure changed')
    inputs = [Path(__file__), ROOT / 'tests/test_window_cache_resident_link.py',
        ROOT / 'tools/graphics_raster_link_audit.py', ROOT / 'tools/graphics_span_bench.py',
        ROOT / 'tools/gen_capability_imports.py', ROOT / 'tools/placement_audit.py',
        ROOT / 'tools/window_cache_controller_delivery.py', ROOT / 'Makefile',
        PROOF / 'SHA256SUMS', PROOF / 'build/build-report.json', transport, binding, driver,
        ROOT / 'src/8502/nmi-common.inc', *sources.values()]
    # Include all normal outputs as a before/after invariant, not only disks.
    baseline_outputs = sorted(p for d in ('build/8502', 'build/boot', 'build/user')
        for p in (ROOT / d).rglob('*') if p.is_file())
    before = {str(p.relative_to(ROOT)): digest(p) for p in baseline_outputs}
    links = {}
    for label, target, cfg in (
            ('normal', 'udeks-8502', '8502-bootstrap'),
            ('panic', 'udeks-8502-panic-probe', '8502-panic-probe')):
        directory = WORK / label; directory.mkdir(exist_ok=True)
        config = ROOT / 'cfg' / (cfg+'.cfg')
        text = retarget_config(config.read_text(), directory)
        (directory / 'kernel.cfg').write_text(text)
        dry = subprocess.check_output(['make', '-Bn', 'build/8502/'+target+'.bin'], cwd=ROOT, text=True)
        command = link_command(dry.replace('cfg/8502-panic-probe.cfg', 'cfg/8502-bootstrap.cfg'))
        inputs += [ROOT / value for value in command if value.endswith('.o')]
        inputs += [config, ROOT / 'build/8502' / (target+'.map')]
        command[command.index('-C')+1] = str(directory / 'kernel.cfg')
        command[command.index('-m')+1] = str(directory / 'kernel.map')
        command[command.index('-o')+1] = str(directory / 'kernel.bin')
        command[command.index('build/8502/vic_graphics_transport.o')] = str(WORK / 'transport.o')
        command += [str(WORK / (n+'.o')) for n in ('raw', 'binding', 'helper')]
        for name in ('_cache_accept_poll', '_private_cache_policy_call', '_cache_step',
                     '_cache_accept_state', '_cache_ticket', '_cache_owner', '_cache_phase'):
            command += ['-u', name]
        subprocess.run(command, cwd=ROOT, check=True)
        baseline = (ROOT / 'build/8502' / (target+'.map')).read_text()
        candidate = (directory / 'kernel.map').read_text()
        if segments(baseline) != segments(candidate):
            raise ValueError('resident segment/ownership drift '+label)
        old_modules = parse_map(baseline)[0]; new_modules = parse_map(candidate)[0]
        helpers = lambda m: {n:s for n,s in m.items() if n.startswith('none.lib(')}
        if helpers(old_modules) != helpers(new_modules):
            raise ValueError('linked runtime helper drift '+label)
        exports = map_exports(candidate)
        fields = {n: exports[n] for n in ('_cache_accept_state', '_cache_ticket', '_cache_owner', '_cache_phase')}
        links[label] = {'command': command, 'segments': segments(candidate),
            'baseline_segments': segments(baseline), 'helpers': helpers(new_modules),
            'baseline_helpers': helpers(old_modules), 'fields': fields,
            'remaining_padding': 131}
    if any(digest(ROOT / n) != sha for n, sha in before.items()):
        raise ValueError('normal provider/output changed during isolated links')
    outputs = sorted(p for p in WORK.rglob('*') if p.is_file() and p.name != 'report.json')
    report = {'qualification': 'isolated resident TRANSPORT link only; UNBOOTABLE stale import bridges; no hooks or calls',
        'charged_bytes': charged, 'remaining_before_hooks': 131, 'objects': objects, 'links': links,
        'cc65': subprocess.check_output(['cc65', '--version'], stderr=subprocess.STDOUT, text=True).strip(),
        'normal_outputs_unchanged': before,
        'inputs_sha256': {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(inputs))},
        'outputs_sha256': {str(p.relative_to(WORK)): digest(p) for p in outputs}}
    (WORK / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('qualification', 'charged_bytes', 'remaining_before_hooks')}, indent=2))


def preserve():
    report = json.loads((WORK / 'report.json').read_text())
    for key, root in (('inputs_sha256', ROOT), ('outputs_sha256', WORK), ('normal_outputs_unchanged', ROOT)):
        for name, sha in report[key].items():
            if digest(root / name) != sha:
                raise ValueError('placement proof drift '+name)
    destination = ROOT / 'bench/artifacts' / NAME
    if destination.exists():
        raise ValueError('refusing to overwrite evidence')
    destination.mkdir(parents=True)
    for key, root, prefix in (('inputs_sha256', ROOT, destination),
                             ('outputs_sha256', WORK, destination / 'build')):
        for name in report[key]:
            target = prefix / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, target)
    shutil.copy2(WORK / 'report.json', destination / 'build/report.json')
    paths = sorted(p for p in destination.rglob('*') if p.is_file())
    (destination / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(destination)}\n' for p in paths))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'preserve'))
    {'build': build, 'preserve': preserve}[parser.parse_args().action]()

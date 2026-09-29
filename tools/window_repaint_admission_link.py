#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Complete isolated normal/panic cost of admission without a second union."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from graphics_raster_link_audit import link_command, segments
from graphics_span_bench import object_sizes
from window_repaint_compact import isolated_config, library_inventory

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/window-repaint-admission'
CALLERS = ROOT / 'build/window-repaint-callers'
SOURCE = ROOT / 'bench/window-repaint-admission'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_object(name, source_name=None, defines=()):
    stem = WORK / name
    source = SOURCE / ((source_name or name) + '.c')
    subprocess.run(['cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99',
                    '-Oirs', *defines, '-I', str(ROOT / 'include'),
                    '-o', str(stem.with_suffix('.s')),
                    str(source)], check=True)
    subprocess.run(['ca65', '-o', str(stem.with_suffix('.o')),
                    str(stem.with_suffix('.s'))], check=True)
    return object_sizes(stem.with_suffix('.o'))


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    prior = json.loads((CALLERS / 'budget.json').read_text())
    objects = {name: compile_object(name) for name in ('admission', 'transaction_damage')}
    objects['admission_bank0'] = compile_object('admission_bank0', 'admission',
                                               ('-DREPAINT_ADMISSION_BANK0_BSS',))
    if objects['admission']['CODE'] != 79 or objects['admission']['HIGHBSS'] != 1 or \
       objects['transaction_damage']['CODE'] != 51 or \
       objects['admission_bank0']['CODE'] != 79 or objects['admission_bank0']['BSS'] != 1:
        raise ValueError('admission object budget changed')
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
        config = directory / 'strict.cfg'
        config_text = isolated_config((ROOT / 'cfg' / cfg).read_text(), directory)
        config.write_text(config_text)
        link = list(command)
        link[link.index('-C') + 1] = str(config)
        link[link.index('-m') + 1] = str(directory / 'kernel.map')
        link[link.index('-o') + 1] = str(directory / 'kernel.bin')
        link[link.index('build/8502/window_manager.o')] = str(CALLERS / 'replacement.o')
        link += [str(CALLERS / (n + '.o')) for n in
                 ('damage', 'receipt', 'binding', 'control')]
        link += [str(WORK / (n + '.o')) for n in ('admission', 'transaction_damage')]
        strict = subprocess.run(link, cwd=ROOT, capture_output=True, text=True)
        if strict.returncode == 0 or \
           "Segment 'HIGHBSS' overflows memory area 'HIGHMEM' by 1 byte" not in strict.stderr:
            raise ValueError('strict HIGHBSS negative gate changed: ' +
                             name + ' ' + strict.stderr[-500:])
        # Sizing ONLY: $E2E2 belongs to selected-task cc65 context. This
        # modified linker region deliberately trespasses by one byte; neither
        # its image nor map may become an OS disk or a placement proposal.
        old_region = 'HIGHMEM: start = $E1B8, size = $012A'
        if config_text.count(old_region) != 1:
            raise ValueError('HIGHMEM ownership changed')
        sizing = directory / 'UNBOOTABLE-sizing.cfg'
        sizing.write_text(config_text.replace(old_region,
                                              'HIGHMEM: start = $E1B8, size = $012B'))
        link[link.index('-C') + 1] = str(sizing)
        subprocess.run(link, cwd=ROOT, check=True)
        text = (directory / 'kernel.map').read_text()
        current = segments(text)
        baseline = prior['links'][name]['segments']
        for segment in ('ZEROPAGE', 'SYSCALLS', 'TASKGATE', 'MODULECODE',
                        'MODULEDATA', 'MODULERODATA', 'BOOTFSCODE', 'TASKREQUEST'):
            if segment in baseline and current[segment] != baseline[segment]:
                raise ValueError('fixed segment moved: ' + name + '/' + segment)
        for segment in ('RODATA', 'DATA', 'BSS', 'VICSHADOW'):
            if current[segment]['size'] != baseline[segment]['size']:
                raise ValueError('unexpected data/bitmap size: ' + name + '/' + segment)
        code_growth = current['CODE']['size'] - baseline['CODE']['size']
        state_growth = current['HIGHBSS']['size'] - baseline['HIGHBSS']['size']
        if (code_growth, state_growth) != (130, 1):
            raise ValueError('unaccounted admission cost: ' + name)
        if library_inventory(text) != library_inventory(
                (CALLERS / name / 'kernel.map').read_text()):
            raise ValueError('new runtime helper: ' + name)
        bank0 = list(link)
        bank0[bank0.index(str(sizing))] = str(config)
        bank0[bank0.index(str(directory / 'kernel.map'))] = str(directory / 'kernel-bank0.map')
        bank0[bank0.index(str(directory / 'kernel.bin'))] = str(directory / 'kernel-bank0.bin')
        bank0[bank0.index(str(WORK / 'admission.o'))] = str(WORK / 'admission_bank0.o')
        subprocess.run(bank0, cwd=ROOT, check=True)
        bank0_text = (directory / 'kernel-bank0.map').read_text()
        bank0_segments = segments(bank0_text)
        for segment in ('ZEROPAGE', 'SYSCALLS', 'TASKGATE', 'MODULECODE',
                        'MODULEDATA', 'MODULERODATA', 'BOOTFSCODE', 'TASKREQUEST'):
            if segment in baseline and bank0_segments[segment] != baseline[segment]:
                raise ValueError('bank0 placement moved fixed segment: ' + name + '/' + segment)
        if bank0_segments['CODE']['size'] - baseline['CODE']['size'] != 130 or \
           bank0_segments['BSS']['size'] - baseline['BSS']['size'] != 1 or \
           bank0_segments['HIGHBSS'] != baseline['HIGHBSS'] or \
           bank0_segments['VICSHADOW']['size'] != baseline['VICSHADOW']['size'] or \
           bank0_segments['VICSHADOW']['start'] != current['VICSHADOW']['start'] + 1 or \
           bank0_segments['BSS']['end'] + 1 != bank0_segments['VICSHADOW']['start'] or \
           bank0_segments['VICSHADOW']['end'] >= 0xCF00:
            raise ValueError('bank0 admission placement/size changed: ' + name)
        if library_inventory(bank0_text) != library_inventory(text):
            raise ValueError('bank0 admission pulled a different runtime helper: ' + name)
        links[name] = {'strict_highbss_rejected_by_one': True,
                       'sizing_config_trespasses_task_context': '$E2E2',
                       'code_growth': code_growth, 'highbss_growth': state_growth,
                       'bank0_strict_link_passes': True,
                       'bank0_bss_growth': 1,
                       'bank0_highbss_growth': 0,
                       'bank0_shadow_start': bank0_segments['VICSHADOW']['start'],
                       'bank0_map_sha256': digest(directory / 'kernel-bank0.map'),
                       'code_growth_over_production':
                       current['CODE']['size'] - prior['links'][name]['segments']['CODE']['size'] +
                       prior['links'][name]['code_growth_over_production'],
                       'map_sha256': digest(directory / 'kernel.map')}
    report = {
        'scope': 'UNBOOTABLE isolated sizing: bank0 BSS owner fits strict link; separate HIGHBSS variant rejects $E2E2; no production caller or test disk',
        'objects': objects, 'links': links,
        'optimistic_resident_deficit_before_callers_provider_delivery':
            prior['budget']['measured_floor'] + 130,
        'state_growth': 1,
        'bank0_owner_lifetime': 'Only manager-context try/release with bank0 mapped; no access while banked policy runs; existing binding masks IRQ during map switch and NMI is record-only; all other entry paths remain unaudited',
        'inputs_sha256': {str(path.relative_to(ROOT)): digest(path) for path in
                          (SOURCE / 'admission.c', SOURCE / 'admission.h',
                           SOURCE / 'transaction_damage.c',
                           ROOT / 'src/services/window/window_manager_cached.c',
                           CALLERS / 'budget.json')},
    }
    (WORK / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        raise

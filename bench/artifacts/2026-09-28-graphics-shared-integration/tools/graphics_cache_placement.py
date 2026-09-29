#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure cache placement against the installed OS, not just its primary map.

This is a budget audit, never a linker change or a cache installation. In
particular, zero-filled scheduler packaging holes are not unowned memory.
Run in the reference container after the normal build prerequisites.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from build_scheduler_overlay import build_overlay, map_segments
from placement_audit import parse_map

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'bench/artifacts/2026-09-28-graphics-cache-placement'
RASTER_FUNCTIONS = ('clear', 'pixel', 'line', 'rectangle', 'fill')


def validate_contracts(header, task_header, configs):
    """Do not silently report the old inventory after a contract edit."""
    expected = {
        'UDEKS_APP1_BASE': 0x0200, 'UDEKS_APP1_LIMIT': 0x0C00,
        'UDEKS_MODULE_CODE_BASE': 0xE300, 'UDEKS_MODULE_CODE_LIMIT': 0xE645,
        'UDEKS_C_STACK_BOTTOM': 0xE700, 'UDEKS_C_STACK_TOP': 0xEFF0,
        'UDEKS_TASK_CONTEXT_BASE': 0xE2E2, 'UDEKS_TASK_CONTEXT_LIMIT': 0xE300,
    }
    constants = {name: int(value, 16) for name, value in re.findall(
        r'^#define\s+(\w+)\s+0x([0-9A-Fa-f]+)u\s*$', header + '\n' + task_header, re.M)}
    expected['UDEKS_TASK_STACK_TOP'] = 0xF7F0
    for name, value in expected.items():
        if constants.get(name) != value:
            raise ValueError(f'{name}: memory contract changed; review inventory')
    for text, area, base, size in configs:
        match = re.search(r'\b' + area + r':\s*start\s*=\s*\$([0-9A-Fa-f]+),'
                          r'\s*size\s*=\s*\$([0-9A-Fa-f]+)', text)
        if match is None or (int(match[1], 16), int(match[2], 16)) != (base, size):
            raise ValueError(f'{area}: linker reservation changed; review inventory')


def listing_functions(text):
    """Read actual assembled CODE offsets, rejecting incomplete/overlap data."""
    active = None
    result = {}
    previous_end = 0
    for line in text.splitlines():
        match = re.match(r'^([0-9A-Fa-f]{6})r?\s+\d+\s+.*?'
                         r'\.(proc|endproc)\b\s*(\w+)?', line)
        if not match:
            continue
        offset, directive, name = match.groups()
        offset = int(offset, 16)
        if directive == 'proc':
            if active is not None or name is None or name in result:
                raise ValueError('nested, unnamed, or duplicate assembly procedure')
            if offset < previous_end:
                raise ValueError('assembly procedure offsets overlap')
            active = (name, offset)
        else:
            if active is None or offset <= active[1]:
                raise ValueError('missing or non-positive assembly procedure')
            result[active[0]] = {'offset': active[1], 'size': offset - active[1]}
            previous_end = offset
            active = None
    if active is not None or not result:
        raise ValueError('incomplete assembly procedure listing')
    return result


def measured_reserve(text, label):
    # ca65 lists the first emitted bytes on the .res line and further bytes
    # on continuation lines. Use the address of the *next* source statement.
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.search(r'\b' + re.escape(label) + r':\s*$', line):
            continue
        start = int(line[:6], 16)
        following = lines[index + 1:]
        size = None
        for item in following:
            match = re.search(r'\.res\s+(\d+),\s*\$ea\b', item, re.I)
            if match:
                size = int(match[1])
                break
            if item[24:].strip():
                raise ValueError(f'{label}: expected a padding reservation')
        if size is None:
            break
        for item in following:
            # Non-continuation source line with a directive after the bytes.
            if '.' in item[24:] and int(item[:6], 16) >= start + size:
                if int(item[:6], 16) != start + size:
                    raise ValueError(f'{label}: reserve extent mismatch')
                return size
    raise ValueError(f'missing measured reserve {label}')


def object_sizes(dump):
    result = {}
    for name, size in re.findall(r'Name:\s*"([^"]+)"\s+Flags:\s*\d+\s+Size:\s*(\d+)', dump):
        if name in result:
            raise ValueError('duplicate object segment')
        result[name] = int(size)
    if not {'CODE', 'BSS'} <= result.keys():
        raise ValueError('missing object CODE/BSS measurement')
    return result


def audit(kernel_map, scheduler_map, context_map, payload, page, tail,
          context, switch, handler, vectors, functions, reserve, object_dumps,
          primitives=None, primitive_reserve=0, shared_reserve=0):
    modules, primary = parse_map(kernel_map)
    primary = {name: (start, end) for name, start, end in primary}
    required = ('VICSHADOW', 'LOWBSS', 'HIGHBSS', 'MODULECODE', 'MODULERODATA')
    if any(name not in primary for name in required):
        raise ValueError('primary map is missing required runtime regions')
    for name, base, limit in (('LOWBSS', 0x0C00, 0x1200),
                              ('HIGHBSS', 0xE1B8, 0xE2E2)):
        start, end = primary[name]
        if start != base or not start <= end < limit:
            raise ValueError(f'{name} exceeds its runtime reservation')
    scheduler = map_segments(scheduler_map)
    contexts = map_segments(context_map)
    # Reconstruct exactly what the current installer consumes. This checks
    # page/tail lengths, BSS, checksums, handler padding and context extensions.
    expected, _ = build_overlay(page, tail, scheduler_map, context, context_map,
                                switch, handler, vectors)
    if expected != payload:
        raise ValueError('installed scheduler payload does not match its inputs')
    if primary['VICSHADOW'] != (0xA1E0, 0xC11F):
        raise ValueError('frozen VIC shadow moved')
    if scheduler['BSS'][1] >= 0xC900:
        raise ValueError('scheduler state overlaps lifecycle handler')
    if not 0 < len(handler) <= 0xCDBD - 0xC900:
        raise ValueError('handler exceeds its qualified reservation')
    if contexts['BSS'][1] != 0xCEFF:
        raise ValueError('context reservation no longer ends at $CEFF')
    if reserve != 49:
        raise ValueError('qualified raster reserve changed')
    graphics = modules['vic_graphics.o']
    if sum(item['size'] for item in functions.values()) != graphics['CODE']:
        raise ValueError('raster listing and resident map disagree')
    candidate = [object_sizes(dump) for dump in object_dumps]
    if len(candidate) != 3:
        raise ValueError('need wrapper, rows and transfer object measurements')
    footprint = sum(sum(item.values()) for item in candidate)
    # No candidate is allowed to quietly acquire another address-space segment.
    for item in candidate:
        if any(size for name, size in item.items() if name not in ('CODE', 'BSS')):
            raise ValueError('candidate gained a non-CODE/BSS allocation')
    primitives = primitives or {}
    if primitives:
        if set(primitives) not in ({'pixel', 'span'}, {'pixel', 'span', 'clear'}) or primitive_reserve != 173:
            raise ValueError('integrated primitives/padding changed; review budget')
        if ('clear' in primitives) != (shared_reserve == 294):
            raise ValueError('shared raster padding/providers changed; review budget')
        for name in primitives:
            if primitives[name] != modules['vic_' + name + '.o']:
                raise ValueError('primitive object and linked map disagree')
            if any(size for segment, size in primitives[name].items() if segment != 'CODE'):
                raise ValueError('primitive gained non-CODE allocation')
        if any('_udeks_vic_bitmap_' + name in functions for name in primitives if name != 'span'):
            raise ValueError('duplicate raster implementation')
    elif primitive_reserve or shared_reserve:
        raise ValueError('padding without measured primitives')
    routines = {}
    for name in RASTER_FUNCTIONS:
        key = '_udeks_vic_bitmap_' + name
        routines[name] = (functions[key]['size'] if key in functions else primitives[name]['CODE'])
    if primitives:
        routines['fill'] += primitives['span']['CODE']
    available = reserve + primitive_reserve + shared_reserve
    post_shadow = 0xCF00 - (primary['VICSHADOW'][1] + 1)
    scheduler_live = scheduler['BSS'][1] - 0xC120 + 1
    context_live = 0xCF00 - 0xCDBD
    padding = 0xC900 - scheduler['BSS'][1] - 1
    handler_slack = 0xCDBD - 0xC900 - len(handler)
    if scheduler_live + padding + len(handler) + handler_slack + context_live != post_shadow:
        raise ValueError('post-shadow ownership does not cover its entire range')
    module_start = primary['MODULECODE'][0]
    module_end = primary['MODULERODATA'][1]
    if not (module_start == 0xE300 and module_end <= 0xE643):
        raise ValueError('module no longer fits current linker allocation')
    return {
        'qualification': 'placement audit only; no resident cache or IRQ/input qualification',
        'candidate': {'code': sum(item['CODE'] for item in candidate),
                      'bss': sum(item['BSS'] for item in candidate),
                      'total': footprint, 'qualified_reserve': available,
                      'additional_bytes_before_bindings': footprint - available},
        'post_shadow': {'base': 0xC120, 'end': 0xCEFF, 'primary_map_gap': post_shadow,
                        'scheduler_code_state': scheduler_live,
                        'scheduler_packaging_padding': padding,
                        'lifecycle_handler': len(handler),
                        'handler_reserved_slack': handler_slack,
                        'context_code_state': context_live,
                        'unowned_bytes': 0},
        'other_regions': [
            {'name': 'low state', 'base': 0x0C00, 'end': 0x11FF,
             'linked_slack': 0x1200 - primary['LOWBSS'][1] - 1,
             'available_to_cache': False},
            {'name': 'high state', 'base': 0xE1B8, 'end': 0xE2E1,
             'linked_slack': 0xE2E2 - primary['HIGHBSS'][1] - 1,
             'available_to_cache': False},
            {'name': 'module linker area', 'base': 0xE300, 'end': 0xE643,
             'linked_slack': 0xE644 - module_end - 1, 'available_to_cache': False},
            {'name': 'module contract extra byte', 'base': 0xE644, 'end': 0xE644,
             'available_to_cache': False},
            {'name': 'module/stack guard', 'base': 0xE645, 'end': 0xE6FF,
             'available_to_cache': False},
            {'name': 'resident software stack', 'base': 0xE700, 'end': 0xEFF0,
             'available_to_cache': False},
            {'name': 'probe/application slot overlap', 'base': 0x0B00, 'end': 0x0BFF,
             'available_to_cache': False},
            {'name': 'transient stack/shared gateway workspace', 'base': 0xF700,
             'end': 0xF7FF, 'available_to_cache': False},
        ],
        'raster_replacement_candidates': routines,
        'raster_code_before_replacements': sum(routines.values()),
        **({'integrated_primitives': primitives,
            'primitive_placement_padding': primitive_reserve} if primitives else {}),
        **({'shared_placement_padding': shared_reserve} if shared_reserve else {}),
        'retained_shell': {name: size for name, size in modules['shell.o'].items()},
        'recommended_path': 'measure in-place ASM raster replacements; retain all public APIs and reservations',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=ROOT / 'build/graphics-cache-placement')
    parser.add_argument('--preserve', action='store_true', help='save a new immutable audit snapshot')
    args = parser.parse_args()
    if args.preserve and EVIDENCE.exists():
        parser.error('evidence already exists; refusing to replace a qualified snapshot')
    work = args.work.resolve()
    if not work.is_relative_to(ROOT / 'build'):
        parser.error('work must be inside this repository build/')
    work.mkdir(parents=True, exist_ok=True)
    inputs = {}

    def read(relative, binary=False):
        data = (ROOT / relative).read_bytes()
        inputs[relative] = hashlib.sha256(data).hexdigest()
        return data if binary else data.decode()

    for relative in ('src/services/display/vic_graphics.c', 'src/8502/vic_graphics.s',
                     'include/udeks/memory.h', 'cfg/8502-bootstrap.cfg',
                     'cfg/8502-scheduler-overlay.cfg', 'cfg/8502-task-context.cfg',
                     'cfg/8502-task-yield-handler.cfg', 'tools/build_scheduler_overlay.py'):
        read(relative)
    validate_contracts(read('include/udeks/memory.h'), read('include/udeks/task.h'), [
        (read('cfg/8502-bootstrap.cfg'), 'MODULE', 0xE300, 0x0344),
        (read('cfg/8502-scheduler-overlay.cfg'), 'PAGE', 0x1C00, 0x0400),
        (read('cfg/8502-scheduler-overlay.cfg'), 'TAIL', 0xC120, 0x0DE0),
        (read('cfg/8502-task-yield-handler.cfg'), 'HANDLER', 0xC900, 0x04BD),
        (read('cfg/8502-task-context.cfg'), 'CONTEXT', 0xCDBD, 0x0143),
    ])
    for name, source in (('raster', 'build/8502/vic_graphics.s'),
                         ('transport', 'src/8502/vic_graphics.s')):
        read(source)
        subprocess.run(['ca65', '--cpu', '6502', '-l', str(work / f'{name}.lst'),
                        '-o', str(work / f'{name}.o'), str(ROOT / source)], check=True)
    cache_source = ROOT / 'bench/window-cache'
    for name in ('cache-fast.c', 'cache.h', 'rows.s', 'transfer-lease.s'):
        read('bench/window-cache/' + name)
    subprocess.run(['cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Oirs',
                    '-I', str(cache_source), '-o', str(work / 'cache.s'),
                    str(cache_source / 'cache-fast.c')], check=True)
    for name, source in (('cache', work / 'cache.s'), ('rows', cache_source / 'rows.s'),
                         ('transfer', cache_source / 'transfer-lease.s')):
        subprocess.run(['ca65', '--cpu', '6502', '-o', str(work / f'{name}.o'),
                        str(source)], check=True)
    dumps = []
    for name in ('cache', 'rows', 'transfer'):
        dump = subprocess.check_output(['od65', '--dump-segments', str(work / f'{name}.o')], text=True)
        (work / f'{name}.segments.txt').write_text(dump)
        dumps.append(dump)
    primitives = {}
    primitive_reserve = 0
    shared_reserve = 0
    if 'raster_primitives_placement_reserve:' in (ROOT / 'src/8502/vic_graphics.s').read_text():
        primitive_reserve = measured_reserve((work / 'transport.lst').read_text(),
                                             'raster_primitives_placement_reserve')
        names = ['pixel', 'span']
        if 'raster_shared_placement_reserve:' in (ROOT / 'src/8502/vic_graphics.s').read_text():
            shared_reserve = measured_reserve((work / 'transport.lst').read_text(), 'raster_shared_placement_reserve')
            names.append('clear')
        for name in names:
            read('src/services/display/vic_' + name + '.s')
            read('build/8502/vic_' + name + '.o', True)
            dump = subprocess.check_output(['od65', '--dump-segments',
                str(ROOT / 'build/8502' / ('vic_' + name + '.o'))], text=True)
            primitives[name] = {key: size for key, size in object_sizes(dump).items() if size}
    report = audit(
        read('build/8502/udeks-8502.map'), read('build/8502/udeks-scheduler-overlay.map'),
        read('build/8502/task-context-binding.map'), read('build/boot/scheduler-overlay.prg', True),
        read('build/8502/udeks-scheduler-overlay-page.bin', True),
        read('build/8502/udeks-scheduler-overlay-tail.bin', True),
        read('build/8502/task-context-binding.bin', True),
        read('build/8502/task-switch-tail.bin', True), read('build/8502/task-yield-handler.bin', True),
        read('build/8502/task-context-vectors.bin', True),
        listing_functions((work / 'raster.lst').read_text()),
        measured_reserve((work / 'transport.lst').read_text(), 'raster_scratch_placement_reserve'), dumps,
        primitives, primitive_reserve, shared_reserve)
    report['inputs_sha256'] = inputs
    report['audit_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['cc65'] = subprocess.check_output(['cc65', '--version'], text=True, stderr=subprocess.STDOUT).strip()
    text = json.dumps(report, indent=2) + '\n'
    (work / 'report.json').write_text(text)
    if args.preserve:
        EVIDENCE.mkdir(parents=True)
        for relative in inputs:
            destination = EVIDENCE / 'inputs' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        for name in ('report.json', 'raster.lst', 'transport.lst',
                     'cache.segments.txt', 'rows.segments.txt', 'transfer.segments.txt'):
            shutil.copyfile(work / name, EVIDENCE / name)
        shutil.copyfile(Path(__file__), EVIDENCE / 'audit.py')
        sums = ''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' +
                       str(path.relative_to(EVIDENCE)) + '\n'
                       for path in sorted(EVIDENCE.rglob('*')) if path.is_file())
        (EVIDENCE / 'SHA256SUMS').write_text(sums)
    print(text, end='')


if __name__ == '__main__':
    main()

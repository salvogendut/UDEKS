#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Link the REAL resident time overlay, without replacing normal boot outputs.

The normal/panic map's object order is preserved and only four objects are
substituted. Every split linker output is redirected under this experiment.
This produces a placement proof, NOT boot disks: boot-only import bridges and
other map-bound delivery artifacts still require a complete candidate build.
"""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from placement_audit import parse_map
from service_image import TIME_BASE, TIME_LIMIT, validate

ROOT = Path(__file__).resolve().parents[1]


def resident_objects(map_text):
    modules, _ = parse_map(map_text)
    objects = [name for name in modules if name.endswith('.o')]
    if len(objects) != len(set(objects)) or any('/' in name for name in objects):
        raise ValueError('unexpected or ambiguous resident object name')
    for name in ('syscall_gate.o', 'time.o', 'service_registry.o', 'time_descriptor.o'):
        if objects.count(name) != 1:
            raise ValueError(f'expected exactly one {name} in resident link')
    return objects


def overlay_config(text, side_directory):
    """No candidate link may overwrite an existing split production output."""
    if 'SERVICEBOOT:' in text:
        raise ValueError('baseline already contains a startup overlay')
    marker = '    VDCASSETS:'
    if text.count(marker) != 1:
        raise ValueError('baseline VDC assets segment changed')
    text = text.replace(marker,
        f'    SERVICEBOOT: load = KERNEL, type = ro, start = ${TIME_BASE:04X}, define = yes;\n'+marker)

    def redirect(match):
        original = match[1]
        if not original:
            return match[0]  # non-emitted BSS/zero page
        if not original.startswith('build/') or '..' in Path(original).parts:
            raise ValueError('unexpected split linker output')
        return f'file = "{side_directory / original}"'

    return re.sub(r'file\s*=\s*"([^"]*)"', redirect, text)


def qualify(baseline, candidate, exports, image):
    required = ('CODE', 'RODATA', 'DATA', 'BSS', 'SERVICEBOOT', 'VDCASSETS')
    if any(name not in candidate for name in required):
        raise ValueError('incomplete candidate segment map')
    for name in ('CODE', 'RODATA', 'DATA', 'BSS'):
        if candidate[name][1] >= TIME_BASE:
            raise ValueError(f'{name} overlaps the time module')
    boot_start, boot_end, _ = candidate['SERVICEBOOT']
    if boot_start != TIME_BASE or boot_end >= TIME_LIMIT:
        raise ValueError('startup overlay exceeds the replacement reservation')
    # This feature may only move the ordinary resident segments and add the
    # startup overlay. No app, stack, VIC, glyph, common-RAM or ZP borrowing.
    moving = {'CODE', 'RODATA', 'DATA', 'BSS'}
    if set(candidate) != set(baseline) | {'SERVICEBOOT'}:
        raise ValueError('unexpected new or missing memory reservation')
    for name, bounds in baseline.items():
        if name not in moving and candidate[name] != bounds:
            raise ValueError(f'protected segment moved: {name}')
    for address, symbol in ((0xcf40, '_udeks_time_slot_set'), (0xcf60, '_udeks_time_now')):
        offset = address-0x2000
        expected = b'\x4c'+exports[symbol][0].to_bytes(2, 'little')
        if image[offset:offset+3] != expected:
            raise ValueError(f'published clock vector ${address:04x} changed')
    if '_udeks_time_sync_ti' in exports:
        raise ValueError('clock-setting policy is still linked into the kernel')
    live_end = candidate['BSS'][1]+1
    return dict(live_end=live_end, remaining_before_slot=TIME_BASE-live_end,
                startup_bytes=candidate['SERVICEBOOT'][2],
                slot_base=TIME_BASE, slot_limit=TIME_LIMIT)


def main():
    out = ROOT/'build/services/time/overlay'
    out.mkdir(parents=True, exist_ok=True)
    report_path = out/'layout.json'
    report_path.unlink(missing_ok=True)

    def run(*args):
        subprocess.run(args, cwd=ROOT, check=True)

    replacements = {}
    for name, source, flags in (
        ('registry', 'src/kernel/service_registry.c', ['-D', 'UDEKS_SERVICE_BOOT_SPLIT']),
        ('resident', 'src/services/time/resident.c', []),
    ):
        target = out/(name+'.o')
        run('cl65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Oirs',
            '-I', 'include', *flags, '-c', '-o', str(target), source)
        replacements[name] = target
    for name, source in (
        ('gateway', 'src/8502/syscall_gate.s'),
        ('core', 'src/services/module/time_slot.s'),
    ):
        target = out/(name+'.o')
        run('ca65', '--cpu', '6502', '-I', 'src/8502', '-D', 'UDEKS_DISK_TIME',
            '-o', str(target), source)
        replacements[name] = target

    forced = []
    for name in ('capability-force-imports.txt', 'boot-console-force-imports.txt'):
        forced += shlex.split((ROOT/'build/8502'/name).read_text())
    for symbol in ('_udeks_bootfs_finish_error', '_udeks_bootfs_finish_ok',
                   '_udeks_line_editor_get_line', '_udeks_banked_pages_init',
                   '_udeks_time_slot_control', '_udeks_time_slot_state', '_udeks_time_slot_request',
                   '_udeks_service_start_phase', '_udeks_service_start_result'):
        forced += ['-u', symbol]
    results = {}
    normal_objects = None
    for variant, suffix, config in (
        ('normal', '', '8502-bootstrap.cfg'),
        ('panic', '-panic-probe', '8502-panic-probe.cfg'),
    ):
        dest = out/variant
        dest.mkdir(parents=True, exist_ok=True)
        map_path, binary = dest/'kernel.map', dest/'kernel.bin'
        map_path.unlink(missing_ok=True)
        binary.unlink(missing_ok=True)
        base_text = (ROOT/f'build/8502/udeks-8502{suffix}.map').read_text()
        objects = []
        for name in resident_objects(base_text):
            if name == 'time.o':
                objects.extend([replacements['core'], replacements['resident']])
            elif name == 'service_registry.o':
                objects.append(replacements['registry'])
            elif name == 'syscall_gate.o':
                objects.append(replacements['gateway'])
            else:
                objects.append(ROOT/'build/8502'/name)
        if variant == 'normal':
            normal_objects = objects
        text = overlay_config((ROOT/'cfg'/config).read_text(), dest)
        cfg = dest/'kernel.cfg'
        cfg.write_text(text)
        for name in re.findall(r'file = "([^"]+)"', text):
            Path(name).parent.mkdir(parents=True, exist_ok=True)
        run('cl65', '-t', 'none', '--cpu', '6502', '-C', str(cfg), '-m', str(map_path),
            '-o', str(binary), *forced, *(str(obj) for obj in objects))
        linked_text = map_path.read_text()
        results[variant] = qualify(map_segments(base_text), map_segments(linked_text),
                                   map_exports(linked_text), binary.read_bytes())
        results[variant]['sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
        # Existing ownership selection/retirement stays in the bounded C880
        # router. Bind only the new private request entry from this exact link.
        bindings = (ROOT/'build/8502/disk-loader-bindings.inc').read_text()
        entry = map_exports(linked_text)['_udeks_time_slot_request'][0]
        (dest/'disk-loader-bindings.inc').write_text(bindings+f'TIME_MODULE_REQUEST = ${entry:04x}\n')
        run('ca65', '-D', 'UDEKS_DISK_TIME', '-I', str(dest),
            '-o', str(dest/'router.o'), 'src/services/filesystem/iec_router.s')
        (dest/'router.cfg').write_text('MEMORY { R: start=$C880,size=$80,file=%O; }\n'
                                       'SEGMENTS { CODE: load=R,type=ro; }\n')
        run('ld65', '-C', str(dest/'router.cfg'), '-o', str(dest/'router.bin'), str(dest/'router.o'))
        results[variant]['router_bytes'] = len((dest/'router.bin').read_bytes())
    normal = map_segments((out/'normal/kernel.map').read_text())
    panic = map_segments((out/'panic/kernel.map').read_text())
    if normal != panic:
        raise ValueError('normal/panic overlay placements differ')
    # Real negative link: one byte past the measured free interval must fail
    # the ld65 assertion. Redirect *all* its side outputs as well; do not
    # damage the successful candidate or production links while testing it.
    negative = out/'overflow'
    negative.mkdir(exist_ok=True)
    padding = negative/'overflow.s'
    padding.write_text('.segment "BSS"\n.res '+str(results['normal']['remaining_before_slot']+1)+'\n')
    run('ca65', '-o', str(negative/'overflow.o'), str(padding))
    cfg_text = overlay_config((ROOT/'cfg/8502-bootstrap.cfg').read_text(), negative)
    (negative/'kernel.cfg').write_text(cfg_text)
    for name in re.findall(r'file = "([^"]+)"', cfg_text):
        Path(name).parent.mkdir(parents=True, exist_ok=True)
    failed = subprocess.run(['cl65', '-t', 'none', '--cpu', '6502',
        '-C', str(negative/'kernel.cfg'), '-o', str(negative/'kernel.bin'),
        *forced, *(str(obj) for obj in normal_objects), str(negative/'overflow.o')],
        cwd=ROOT, capture_output=True, text=True)
    (negative/'link.log').write_text(failed.stdout+failed.stderr)
    if not failed.returncode or 'resident reaches time-service overlay' not in failed.stderr:
        raise AssertionError('overflow negative link did not trip the resident bound')
    module = validate((out.parent/'TIME.SVC').read_bytes())
    results['module'] = module
    results['negative_link'] = 'one-byte overflow rejected by resident assertion'
    results['scope'] = 'actual resident link; NOT a disk-loading or boot-image qualification'
    report_path.write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()

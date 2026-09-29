#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate and preserve emulator evidence for the installed span/pixel service.

Run after the documented clean build and disk probes. This never starts an
emulator, changes an image, or replaces previously preserved evidence.
"""
import argparse
import hashlib
import importlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from graphics_span_bench import ROOT, digest
from graphics_raster_link_audit import segments, reference_segments
from graphics_raster_bench_run import emulator_provenance
from placement_audit import parse_map, sizes_from_object_dump
from gen_capability_imports import map_exports

NAME = '2026-09-28-graphics-primitives-integration'
EXPECTED_DISKS = {
    'udeks.d71': 'a8d3272d9789b2b125a52dd5c89a1ecb9a9ea28c2486c20af25055ee9af44e06',
    'udeks.d64': 'c5d161a6823622e8678fa843511cf1061ce970a9b3f12bd3ce3240de233c52c7',
}
SHARED_NAME = '2026-09-28-graphics-shared-integration'
SHARED_DISKS = {
    'udeks.d71': 'de666c9e1b8dffcc7b92bc1912bc19f3a2e7da2daf688b6b6bb7596cb389e599',
    'udeks.d64': '32f8e83f77629c3db8396cbc23ad3867f8fa1f951fcb689ad7b84c7dd838989a',
}


def stress_result(text):
    if 'PASS: repeated native wave drags and console cancellation' not in text:
        raise ValueError('missing drag-stress completion')
    rows = re.findall(r'^stress (\d+):.*release=(\d+) frames$', text, re.M)
    if [int(i) for i, _ in rows] != list(range(32)):
        raise ValueError('missing or duplicate drag samples')
    replay = re.search(r'replay: completed in (\d+) PAL frames after last release; leases=(\d+)', text)
    latency = re.search(r'drag release max partial=(\d+) cached=(\d+); completed-wave cancellation=(\d+)', text)
    if not replay or not latency or int(replay[2]) != 21:
        raise ValueError('incomplete replay/latency evidence')
    measured = [int(value) for _, value in rows]
    if max(measured[:16]) != int(latency[1]) or max(measured[16:]) != int(latency[2]):
        raise ValueError('drag latency summary disagrees with samples')
    return dict(partial=int(latency[1]), cached=int(latency[2]), cancellation=int(latency[3]),
                remaining_replay=int(replay[1]), leases=int(replay[2]))


def validate_layout(normal, panic, dump, shared=False):
    baseline = reference_segments()
    current = segments(normal)
    if set(current) != set(baseline) or segments(panic) != current:
        raise ValueError('normal/panic segment parity changed')
    for name in current:
        if name not in ('CODE', 'RODATA', 'DATA', 'BSS') and current[name] != baseline[name]:
            raise ValueError(f'frozen {name} segment moved')
    if current['VICSHADOW'] != dict(start=0xA1E0, end=0xC11F, size=8000):
        raise ValueError('shadow placement changed')
    bss_reduction = 6 if shared else 3
    if current['BSS']['end'] != baseline['BSS']['end'] or current['BSS']['size'] != baseline['BSS']['size'] - bss_reduction:
        raise ValueError('unexpected resident BSS change')
    if current['CODE']['size'] != baseline['CODE']['size'] + bss_reduction:
        raise ValueError('named padding no longer preserves linked extent')
    modules = parse_map(normal)[0]
    if modules['vic_graphics.o'] != {'CODE': 3453 if shared else 3796, 'BSS': 26 if shared else 29, 'VICSHADOW': 8000}:
        raise ValueError('display C footprint changed')
    if modules['vic_span.o'] != {'CODE': 102} or modules['vic_pixel.o'] != {'CODE': 190}:
        raise ValueError('qualified assembly footprint changed')
    if shared and modules.get('vic_clear.o') != {'CODE': 52}:
        raise ValueError('qualified clear footprint changed')
    sizes = sizes_from_object_dump(dump)
    if sizes != [254, 46, 68, 358]:
        raise ValueError('copied common gateways changed')
    zp = dict(sp=0x06, sreg=0x08, regsave=0x0A, ptr1=0x0E, ptr2=0x10,
              ptr3=0x12, ptr4=0x14, tmp1=0x16, tmp2=0x17, tmp3=0x18,
              tmp4=0x19, regbank=0x1A)
    for text in (normal, panic):
        exports = map_exports(text)
        for name, address in zp.items():
            if exports.get(name) != (address, 'RLZ'):
                raise ValueError(f'UAPP runtime {name} moved')
    return dict(segments=current, gateway_sizes=sizes, display_code=3797 if shared else 4088,
                display_bss=26 if shared else 29, net_saved=467 if shared else 173,
                held_padding=467 if shared else 173, runtime_zp=zp)


def qualify(preserve, shared=False):
    name = SHARED_NAME if shared else NAME
    prefix = 'shared' if shared else 'raster-primitives'
    disks = SHARED_DISKS if shared else EXPECTED_DISKS
    artifacts = ROOT / 'bench/artifacts' / name
    results = ROOT / 'bench/results' / name
    if preserve and (artifacts.exists() or results.exists()):
        raise ValueError('refusing to overwrite preserved evidence')
    dump = subprocess.check_output(['od65', '--dump-exports', 'build/8502/vic_graphics_transport.o'], text=True)
    report = validate_layout((ROOT / 'build/8502/udeks-8502.map').read_text(),
                             (ROOT / 'build/8502/udeks-8502-panic-probe.map').read_text(), dump, shared)
    for name, expected in disks.items():
        if digest(ROOT / 'build/boot' / name) != expected:
            raise ValueError('disk differs from clean-build qualification; rerun gates')
    report['disk_sha256'] = disks
    report['native'] = {label: stress_result((ROOT / f'build/{prefix}-{label}.log').read_text())
                        for label in ('baseline', 'd71', 'd64')}
    if report['native']['d71'] != report['native']['d64']:
        raise ValueError('native disk-format results differ')
    if 'PASS: native boot, stable idle, typing/backspace/history' not in (
            ROOT / f'build/{prefix}-input.log').read_text():
        raise ValueError('normal input smoke missing')
    for label in ('d71', 'd64'):
        text = (ROOT / f'build/{prefix}-vice-{label}.log').read_text()
        if 'task-YIELD probe OK' not in text or 'xwave complete, 21 cached rows' not in text:
            raise ValueError('VICE app/scheduler smoke missing')
    shadow_dir = ROOT / f'build/vice/{prefix}-shadow'
    if 'shadow probe OK' not in (ROOT / f'build/{prefix}-shadow.log').read_text():
        raise ValueError('shadow/installed-tail gate missing')
    shadow = (shadow_dir / 'shadow-drawn.bin').read_bytes()
    bitmap = (shadow_dir / 'vic-bitmap.bin').read_bytes()
    # shadow_boot_probe normalizes its final bitmap files to raw payloads.
    if len(shadow) != 8000 or len(bitmap) != 8000 or shadow != bitmap:
        raise ValueError('shadow and bank-1 bitmap differ')
    report['bitmap_payload_sha256'] = hashlib.sha256(shadow).hexdigest()
    report['physical_hardware'] = 'pending; no acceptance claimed'
    report['pixel_cache'] = 'not installed; unchanged-size moves still replay cached vertices'
    sources = importlib.import_module('1986_input_smoke_build').emulator_sources(ROOT.parent / '1986')
    provenance = emulator_provenance(ROOT.parent / '1986', sources)
    reference_kind = 'graphics-shared' if shared else 'graphics-pixel'
    reference_provenance = json.loads((ROOT / f'bench/results/2026-09-28-{reference_kind}/1986-provenance.json').read_text())
    if provenance != reference_provenance:
        raise ValueError('1986 inputs changed since qualification; rerun and refresh provenance')
    report['1986'] = provenance
    # Flatpak is host-owned; od65 is container-owned. Capture the host identity
    # before invoking this tool in the reference container.
    report['VICE'] = (ROOT / f'build/{prefix}-VICE-flatpak.txt').read_text()
    if report['VICE'] != (ROOT / f'bench/results/2026-09-28-{reference_kind}/VICE-flatpak.txt').read_text():
        raise ValueError('VICE identity changed since qualification')
    placement = json.loads((ROOT / 'build/graphics-cache-placement/report.json').read_text())
    if placement['candidate']['qualified_reserve'] != (516 if shared else 222) or placement['candidate']['additional_bytes_before_bindings'] != (507 if shared else 801):
        raise ValueError('updated cache-placement budget missing')
    artifact_inputs = [f'build/boot/{name}' for name in disks] + [
        'build/8502/udeks-8502.map', 'build/8502/udeks-8502-panic-probe.map',
        'src/services/display/vic_graphics.c', 'src/services/display/vic_span.s',
        'src/services/display/vic_pixel.s', 'src/8502/vic_graphics.s', 'Makefile',
        'tools/1986_input_smoke.c', 'tools/1986_input_smoke_build.py',
        'tools/graphics_primitives_qualify.py', 'tools/graphics_cache_placement.py',
        'build/8502/capability-bridge.s', 'build/8502/boot-console-bridge.s',
        'build/8502/scheduler-overlay-bridge.s']
    if shared:
        artifact_inputs += ['src/services/display/vic_clear.s', 'bench/graphics-shared/line.c',
                            'bench/graphics-shared/rectangle.c', 'tools/graphics_shared_bench.py']
    result_inputs = [f'build/{prefix}-{label}.log' for label in (
        'baseline', 'd71', 'd64', 'input', 'vice-d71', 'vice-d64', 'shadow')] + [
        'build/graphics-cache-placement/report.json', f'build/{prefix}-VICE-flatpak.txt'] + [
        str(path.relative_to(ROOT)) for path in sorted(shadow_dir.iterdir()) if path.is_file()]
    if preserve:
        artifacts.mkdir(parents=True); results.mkdir(parents=True)
        for directory, paths in ((artifacts, artifact_inputs), (results, result_inputs)):
            for relative in paths:
                target = directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
        (results / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
        (results / 'gateway-exports.txt').write_text(dump)
        for directory in (artifacts, results):
            (directory / 'SHA256SUMS').write_text(''.join(digest(path) + '  ' + str(path.relative_to(directory)) + '\n'
                for path in sorted(directory.rglob('*')) if path.is_file() and path.name != 'SHA256SUMS'))
    print(json.dumps({key: report[key] for key in ('disk_sha256', 'native', 'net_saved', 'gateway_sizes')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preserve', action='store_true')
    parser.add_argument('--shared', action='store_true', help='qualify the follow-on shared-raster checkpoint')
    args = parser.parse_args()
    qualify(args.preserve, args.shared)

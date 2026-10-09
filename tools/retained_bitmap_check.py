#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the installed bitmap service against the target proof and real maps."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from build_window_cache import layout_maps
from build_scheduler_overlay import map_segments
from graphics_code_budget import resident_gap, sizes
from placement_audit import parse_map

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'build/bitmap-store'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    normal = ROOT/'build/8502/udeks-8502.map'
    panic = ROOT/'build/8502/udeks-8502-panic-probe.map'
    segments = layout_maps(normal.read_text(), panic.read_text())
    modules, _ = parse_map(normal.read_text())
    linked = modules['retained_pool.o']
    tested = sizes(WORK/'pool-test.o')
    if linked != {'BSS': 5, 'GRAPHICSCODE': 154} or tested.get('CODE') != 154 or tested.get('BSS') != 5:
        raise ValueError('shared pool target/production size mismatch; requalify')
    candidate = sizes(WORK/'retained.o')
    painter = sizes(ROOT/'build/8502/retained_bitmap_paint.o')
    if modules.get('retained_bitmap.o') != {k:v for k,v in candidate.items() if v}:
        raise ValueError('target-tested C handler differs from installed handler')
    if modules.get('retained_bitmap_paint.o') != {k:v for k,v in painter.items() if v}:
        raise ValueError('target-tested painter differs from installed painter')
    if 'bitmap_store.o' in modules:
        raise ValueError('portable reference must not duplicate the resident allocator')
    simulated = map_segments((WORK/'retained-check.map').read_text())
    if simulated['POOL'] != (0x1300, 0x1bff, 2304):
        raise ValueError('simulated pool must occupy the real service addresses')
    result = subprocess.check_output(['sim65', str(WORK/'retained-check')], text=True, timeout=60)
    match = re.fullmatch(r'PASS (\d+) retained bitmap checks: shared allocator, request parity and pixels\n', result)
    if not match or int(match[1]) < 22000:
        raise ValueError('missing complete target proof')
    (WORK/'retained-check.log').write_text(result)
    gap = resident_gap(segments)
    if gap<16: raise ValueError('bitmap integration leaves less than its 16-byte floor')
    sources = ['Makefile', 'src/services/window/retained_paths.c',
        'src/services/window/retained_pool.s', 'src/services/window/retained_bitmap.c',
        'src/services/window/retained_bitmap_paint.s','src/services/window/banked_graphics.c',
        'src/8502/syscall_gate.s','src/services/console/vdc_console.c',
        'src/services/terminal/line_editor.c','src/services/display/vic_graphics.c',
        'src/services/window/bitmap_store.c', 'include/udeks/retained_paths.h',
        'include/udeks/retained_bitmap.h', 'include/udeks/bitmap_store.h',
        'include/udeks/task_request.h', 'include/udeks/vic_graphics.h',
        'bench/packed-bitmap/retained_check.c', 'bench/packed-bitmap/retained_sim.cfg',
        'tools/retained_bitmap_check.py', 'tools/graphics_code_budget.py',
        'tests/test_retained_bitmap.py', 'tests/fixtures/retained_bitmap.c',
        'tests/test_banked_graphics.py','tests/fixtures/banked_graphics.c',
        'tools/bitmap_service_probe.py','bench/packed-bitmap/client.c',
        'build/8502/udeks-8502.map', 'build/8502/udeks-8502-panic-probe.map',
        'build/8502/retained_pool.o', 'build/bitmap-store/pool-test.o',
        'build/8502/retained_bitmap_paint.o',
        'build/bitmap-store/retained.o', 'build/bitmap-store/retained-check',
        'build/bitmap-store/retained-check.map']
    report = dict(scope='UTRQ 0.20 bitmap service installed; xview unchanged',
        target_checks=int(match[1]), pool_address=0x1300, pool_bytes=2304,
        linked_allocator=linked, linked_request=candidate,linked_painter=painter,
        resident_free_bytes=gap,
        compiler_profiles={name:modules[name+'.o'] for name in ('vdc_console','line_editor','vic_graphics')},
        graphics_segment_free=0x1300-segments['GRAPHICSCODE'][1]-1,
        path_segment_free=0x9aa8-segments['GRAPHICSPATHS'][1]-1,
        normal_panic_layout_equal=True,
        cc65=subprocess.check_output(['cc65', '--version'], stderr=subprocess.STDOUT, text=True).strip(),
        source_and_build_sha256={name:digest(ROOT/name) for name in sources},
        disk_sha256={suffix:digest(ROOT/('build/boot/udeks.'+suffix)) for suffix in ('d64','d71','d81')})
    (WORK/'integration-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(result, end='')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

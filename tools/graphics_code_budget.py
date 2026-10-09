#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure and qualify the selective WM compiler-profile space reclaim.

Run in the reference container after boot/graphics-apps-check. The simulator
compares complete drawing/state traces, not hashes alone. It does not model
VIC timing: live VICE/1986 regressions remain separate gates.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from build_window_cache import layout_maps
from placement_audit import parse_map

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/bitmap-store/code-budget'
SOURCE = ROOT / 'src/services/window/window_manager_cached.c'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def compare_sizes(reference, candidate, linked):
    """Charge every non-code segment and require the measured object in boot."""
    def state(sizes):
        return {key: value for key, value in sizes.items() if key != 'CODE' and value}
    if state(reference) != state(candidate):
        raise ValueError('compiler profile changed state/data reservations')
    if {k: v for k, v in candidate.items() if v} != {k: v for k, v in linked.items() if v}:
        raise ValueError('production link does not contain the measured manager')
    saved = reference['CODE'] - candidate['CODE']
    if saved <= 0:
        raise ValueError('compiler profile did not reclaim code')
    return saved


def resident_gap(segments):
    """Only ordinary resident slack counts; never retired overlays/guards."""
    gap = segments['SERVICEBOOT'][0] - segments['BSS'][1] - 1
    if gap < 0:
        raise ValueError('resident overlaps time-service reservation')
    return gap


def split_trace(output):
    # sim65 -c appends its ASCII counter to stdout after the binary trace.
    match = re.search(rb'([0-9]+) cycles\n$', output)
    if not match or not match.start() or match.start() % 2:
        raise ValueError('missing simulator counter or malformed word trace')
    return output[:match.start()], int(match[1])


def sizes(path):
    dump = subprocess.check_output(['od65', '--dump-segments', str(path)], text=True)
    return {name: int(size) for name, size in re.findall(
        r'Name:\s*"([^"]+)"\s+Flags:\s*\d+\s+Size:\s*(\d+)', dump)}


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    def run(*args):
        subprocess.run(list(map(str, args)), cwd=ROOT, check=True)
    flags = ['-t', 'none', '--cpu', '6502', '--standard', 'c99', '-I', 'include']
    # Compile the driver/lease once so only manager code generation differs.
    run('cl65', '-t', 'sim6502', '--standard', 'c99', '-Os', '-I', 'include',
        '-c', '-o', WORK/'trace.o', 'bench/packed-bitmap/wm_trace.c')
    run('cl65', '-t', 'sim6502', '--standard', 'c99', '-Os', '-I', 'include',
        '-c', '-o', WORK/'lease.o', 'src/services/window/move_cache_state.c')
    traces, measured, cycles = {}, {}, {}
    for name, profile in (('baseline', '-Oirs'), ('compact', '-Ors')):
        run('cc65', *flags, profile, '-o', WORK/(name+'.s'), SOURCE)
        run('ca65', '--cpu', '6502', '-o', WORK/(name+'.o'), WORK/(name+'.s'))
        measured[name] = sizes(WORK/(name+'.o'))
        run('cc65', *flags, profile, '-o', WORK/(name+'-unit.s'), 'bench/packed-bitmap/wm_unit.c')
        run('ca65', '--cpu', '6502', '-o', WORK/(name+'-unit.o'), WORK/(name+'-unit.s'))
        run('cl65', '-t', 'sim6502', '-C', 'bench/packed-bitmap/wm_sim.cfg',
            '-o', WORK/name, WORK/(name+'-unit.o'), WORK/'trace.o', WORK/'lease.o')
        output = subprocess.check_output(['sim65', '-c', str(WORK/name)], timeout=60)
        traces[name], cycles[name] = split_trace(output)
        (WORK/(name+'.trace')).write_bytes(traces[name])
    if traces['baseline'] != traces['compact']:
        raise ValueError('drawing/transport/state trace changed')
    normal = (ROOT/'build/8502/udeks-8502.map').read_text()
    panic = (ROOT/'build/8502/udeks-8502-panic-probe.map').read_text()
    segments = layout_maps(normal, panic)  # all existing lifetime/ABI bounds
    modules, _ = parse_map(normal)
    saved = compare_sizes(measured['baseline'], measured['compact'], modules['window_manager.o'])
    gap = resident_gap(segments)
    if gap < 800:
        raise ValueError('placement increment reclaimed less than its 800-byte floor')
    report = dict(scope='WM code-space reclaim only; bitmap core remains unlinked',
        profiles={'baseline': '-Oirs', 'compact': '-Ors'}, objects=measured,
        object_code_saved=saved, resident_free_bytes=gap,
        trace_bytes=len(traces['baseline']), trace_sha256=digest(traces['baseline']),
        simulated_cycles_including_trace_stubs=cycles,
        normal_panic_layout_equal=True,
        cc65=subprocess.check_output(['cc65', '--version'], stderr=subprocess.STDOUT, text=True).strip(),
        input_sha256={str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in (
            SOURCE, ROOT/'Makefile', Path(__file__),
            ROOT/'bench/packed-bitmap/wm_unit.c', ROOT/'bench/packed-bitmap/wm_trace.c',
            ROOT/'bench/packed-bitmap/wm_sim.cfg', ROOT/'src/services/window/move_cache_state.c',
            ROOT/'build/8502/udeks-8502.map', ROOT/'build/8502/udeks-8502-panic-probe.map')},
        disk_sha256={suffix: digest((ROOT/('build/boot/udeks.'+suffix)).read_bytes())
                     for suffix in ('d64', 'd71', 'd81')})
    (WORK/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

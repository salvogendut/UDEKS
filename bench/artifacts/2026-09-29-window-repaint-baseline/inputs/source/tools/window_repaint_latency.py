#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure input-service gaps on the accepted default disks without OS patches.

This first checkpoint deliberately rejects changed disks. It is the reference
measurement, not a builder, a new compositor, or a candidate acceptance gate.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

from gen_capability_imports import map_exports
from graphics_raster_bench_run import emulator_provenance
from window_cache_manager import replace
from window_drag_latency import instrument

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'bench/results/2026-09-29-window-cache-integration'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(native, symbols):
    """Extend the source-bound accepted input harness, never a private OS clone."""
    text = instrument(native)
    include = (ROOT / 'bench/window-cache-manager/repaint-latency.inc').read_text()
    marker = 'static void profile_stop(void) {'
    definitions = '\n'.join(f'#define REPAINT_{label}_PC 0x{symbols[name][0]:04x}u'
        for label, name in (('MANAGER', '_udeks_window_manager_poll'),
                            ('KEYBOARD', '_udeks_keyboard_poll')))
    text = replace(text, marker, definitions + '\n' + include + '\n' + marker)
    text = replace(text, '    if(pc==CLOCK_SET && clock_armed) {',
                   '    if(repaint_stop(pc))return;\n    if(pc==CLOCK_SET && clock_armed) {')
    text = replace(text, '    unsigned clock_finish=word(0xF25A);drag_release(clock_finish);',
                   '    repaint_begin(100);\n    unsigned clock_finish=word(0xF25A);drag_release(clock_finish);')
    text = replace(text, '    frames(300);require(byte(CACHE_PHASE)==0,"clock-only drag retained a cache");',
                   '    frames(300);repaint_finish(100);require(byte(CACHE_PHASE)==0,"clock-only drag retained a cache");')
    text = replace(text, '        profile_begin();', '        repaint_begin(i);profile_begin();')
    text = replace(text, '        profile_end(i);', '        repaint_finish(i);profile_end(i);')
    for prefix in ('clock', 'overlap clock'):
        marker = f'    printf("{prefix} drag start: frames=%u\\n",(unsigned)c128_frame_count-clock_start);'
        text = replace(text, marker,
            f'    require((unsigned)c128_frame_count-clock_start<=30,"{prefix} drag-start exceeded 30 frames");\n' + marker)
    text = replace(text, '    clock_finish=word(0xF25A);drag_release(clock_finish);frames(300);',
                   '    repaint_begin(101);clock_finish=word(0xF25A);drag_release(clock_finish);frames(300);')
    assertion = ('    require(memcmp(machine->mem.ram+0xA1E0,machine->mem.ram+0x16000,8000)==0,\n'
                 '        "clock drag left shadow/VIC disagreement");')
    return replace(text, assertion, '    repaint_finish(101);\n' + assertion)


def measurements(log):
    found = re.findall(r'^repaint service: case=(\d+) service=(manager|keyboard) calls=(\d+) '
        r'retries=(\d+) max_call=(\d+) max_gap=(\d+) span=(\d+)$', log, re.M)
    expected = {(i, service) for i in (*range(16), 100, 101) for service in ('manager', 'keyboard')}
    result = {}
    for case, service, calls, retries, call, gap, span in found:
        key = (int(case), service)
        values = dict(zip(('calls', 'retries', 'max_call_bus_cycles', 'max_gap_bus_cycles',
                          'span_bus_cycles'), map(int, (calls, retries, call, gap, span))))
        if key in result or values['calls'] == 0 or not 0 < int(call) <= int(span) or \
                not 0 < int(gap) <= int(span):
            raise ValueError('duplicate or invalid repaint measurement')
        result[key] = {'case': key[0], 'service': service, **values}
    if set(result) != expected or 'PASS: native clock-only/overlap drag-start timing and shutdown' not in log:
        raise ValueError('incomplete repaint measurement/input shutdown gate')
    for case in (*range(16), 100, 101):
        if result[(case, 'manager')]['span_bus_cycles'] != result[(case, 'keyboard')]['span_bus_cycles']:
            raise ValueError('service spans disagree')
    return [result[key] for key in sorted(result)]


def run(build_root, emulator, output):
    build_root, emulator, output = build_root.resolve(), emulator.resolve(), output.resolve()
    report = json.loads((REFERENCE / 'report.json').read_text())
    original = REFERENCE / 'native.c'
    native_run = json.loads((REFERENCE / '1986-run.json').read_text())
    if digest(original) != native_run['source_sha256']:
        raise ValueError('reference harness drift')
    kernel = build_root / 'build/8502/udeks-8502.bin'
    if digest(kernel) != report['inputs_sha256']['build/8502/udeks-8502.bin']:
        raise ValueError('this checkpoint requires the accepted baseline kernel')
    disks = {fmt: build_root / f'build/boot/udeks.{fmt}' for fmt in ('d71', 'd64')}
    if {fmt: digest(path) for fmt, path in disks.items()} != report['disk_sha256']:
        raise ValueError('this checkpoint requires the accepted baseline disks')
    kernel_map = build_root / 'build/8502/udeks-8502.map'
    symbols = map_exports(kernel_map.read_text())
    for macro, symbol in (('PROFILE_PAGE', '_udeks_vic_bitmap_commit_page'),
                          ('PROFILE_DISABLE', '_udeks_vic_graphics_disable'), ('CLOCK_CACHE_PHASE', '_cache_phase')):
        match = re.search(r'^#define ' + macro + r' 0x([0-9a-f]+)u$', original.read_text(), re.M)
        if match is None or int(match[1], 16) != symbols[symbol][0]:
            raise ValueError('reference profiler binding changed: ' + macro)
    inputs = [Path(__file__), ROOT / 'tools/window_drag_latency.py',
              ROOT / 'bench/window-cache-manager/repaint-latency.inc', original,
              REFERENCE / 'report.json', REFERENCE / '1986-run.json', kernel, kernel_map, *disks.values()]
    input_hashes = {str(path): digest(path) for path in inputs}
    builder = importlib.import_module('1986_input_smoke_build')
    emulator_sources = builder.emulator_sources(emulator)
    provenance = emulator_provenance(emulator, emulator_sources)
    output.mkdir(parents=True, exist_ok=True)
    code = output / 'native.c'
    code.write_text(source(original.read_text(), symbols))
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'sdl3'], text=True))
    runner = output / 'native'
    subprocess.run(['cc', '-std=gnu11', '-O2', '-I' + str(emulator / 'src'), str(code),
                    *map(str, emulator_sources), *flags, '-lm', '-o', str(runner)], check=True)
    environment = os.environ.copy()
    environment.update(UDEKS_DRAG_STRESS='16', UDEKS_DRAG_CLOCK='1')
    results = {}
    for fmt, disk in disks.items():
        process = subprocess.run([str(runner), str(emulator / 'roms'), str(disk),
            builder.slot_address(build_root / 'build/8502/udeks-scheduler-overlay.map'),
            str(output / f'{fmt}.vsf')], env=environment, text=True, capture_output=True)
        log = output / (fmt + '.log')
        log.write_text(process.stdout + process.stderr)
        if process.returncode:
            raise ValueError('repaint profiler failed: ' + str(log))
        results[fmt] = measurements(log.read_text())
    if emulator_provenance(emulator, emulator_sources) != provenance or \
            {str(path): digest(path) for path in inputs} != input_hashes:
        raise ValueError('inputs changed during repaint profiling')
    record = {'scope': 'baseline read-only native mouse/service-entry-return probes; no OS patches',
              'time_unit': 'emulated bus cycles, includes interrupts and CPU handoffs',
              'build_root': str(build_root), 'source_root': str(ROOT),
              'provenance': provenance, 'input_sha256': input_hashes,
              'source_sha256': digest(code), 'runner_sha256': digest(runner),
              'log_sha256': {fmt: digest(output / (fmt + '.log')) for fmt in results}, 'results': results}
    (output / 'run.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({fmt: {service: max(item['max_gap_bus_cycles'] for item in values
        if item['service'] == service) for service in ('manager', 'keyboard')}
        for fmt, values in results.items()}, indent=2))


def preserve(output):
    """Keep source/log/binary provenance, never ROM-bearing snapshots."""
    record = json.loads((output / 'run.json').read_text())
    for path, sha in record['input_sha256'].items():
        if digest(Path(path)) != sha:
            raise ValueError('baseline input drift: ' + path)
    for fmt, sha in record['log_sha256'].items():
        if digest(output / (fmt + '.log')) != sha or measurements((output / (fmt + '.log')).read_text()) != record['results'][fmt]:
            raise ValueError('baseline log/measurement drift: ' + fmt)
    for name, key in (('native.c', 'source_sha256'), ('native', 'runner_sha256')):
        if digest(output / name) != record[key]:
            raise ValueError('baseline runner drift: ' + name)
    name = '2026-09-29-window-repaint-baseline'
    artifact, result = ROOT / 'bench/artifacts' / name, ROOT / 'bench/results' / name
    if artifact.exists() or result.exists():
        raise ValueError('refusing to overwrite baseline evidence')
    retained = {}
    for path in record['input_sha256']:
        path = Path(path)
        if path.is_relative_to(ROOT):
            target = artifact / 'inputs/source' / path.relative_to(ROOT)
        elif path.is_relative_to(Path(record['build_root'])):
            target = artifact / 'inputs/build' / path.relative_to(record['build_root'])
        else:
            raise ValueError('unknown baseline input ownership: ' + str(path))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        retained[str(path)] = str(target.relative_to(artifact))
    result.mkdir(parents=True)
    (result / 'preserved-inputs.json').write_text(json.dumps(retained, indent=2) + '\n')
    for name in ('run.json', 'native.c', 'd71.log', 'd64.log'):
        shutil.copy2(output / name, result / name)
    shutil.copy2(output / 'native', artifact / 'native')
    for directory in (artifact, result):
        files = sorted(path for path in directory.rglob('*') if path.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(
            f'{digest(path)}  {path.relative_to(directory)}\n' for path in files))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-root', type=Path, default=ROOT)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/repaint-latency-baseline')
    parser.add_argument('--preserve', action='store_true', help='archive successful source-bound results without ROM snapshots')
    args = parser.parse_args()
    run(args.build_root, args.emulator, args.output)
    if args.preserve:
        preserve(args.output.resolve())

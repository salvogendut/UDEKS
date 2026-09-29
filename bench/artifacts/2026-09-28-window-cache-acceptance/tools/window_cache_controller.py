#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure/qualify the direct bank-1 continuation; never installs GUI caching."""
import argparse
import hashlib
import importlib
import json
import shlex
import re
import shutil
import subprocess
from pathlib import Path
import window_cache_command as base

ROOT = base.ROOT
WORK = ROOT / 'build/bench/window-cache-controller'
SOURCE = ROOT / 'bench/window-cache-controller'
NAME = '2026-09-28-window-cache-controller'
CASES = (0, 1, 'irq-leak', 'zp-leak', 'shell-stack', 'no-pending')

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def build():
    from graphics_span_bench import object_sizes
    from placement_audit import parse_map
    WORK.mkdir(parents=True, exist_ok=True)
    layout = (SOURCE / 'layout.inc').read_text()
    # Stop rather than allow assembly/C addresses to diverge on a layout edit.
    expected = {'LEASE': '$5220', 'ROW': 'LEASE+13', 'FLOW': 'ROW+9',
        'STACK_BOTTOM': '$5250', 'STACK_TOP': 'STACK_BOTTOM+$f0',
        'CACHE': '$5350', 'CACHE_LIMIT': '$5c00', 'DISPATCH': '$42d5'}
    assignments = dict(re.findall(r'^(\w+)\s*=\s*(.+)$', layout, re.M))
    if any(assignments.get(n) != value for n, value in expected.items()):
        raise ValueError('assembly/C controller layout disagreement')
    # The fixed proposal is accepted only after measuring the entire closure.
    defines = ['UDEKS_CACHE_LEASE_ADDRESS=0x5220u', 'UDEKS_CACHE_ROW_ADDRESS=0x522Du',
        'UDEKS_CACHE_FLOW_ADDRESS=0x5236u', 'UDEKS_CACHE_IMAGE_ADDRESS=0x5350u',
        'UDEKS_CACHE_IMAGE_CAPACITY=2224u', 'UDEKS_CACHE_FLOW_IN_BANK']
    module = (base.SOURCE / 'module.s').read_text().replace(
        '_udeks_cache_overlay_command', '_udeks_cache_controller')
    module = module.replace('row_state: .res 9', 'row_state: .res 9\nflow_state: .res 4')
    module += '\n        .assert flow_state = FLOW, error, "flow state moved"\n'
    (WORK / 'module.s').write_text(module)
    # ca65 searches the source's own directory before -I. Copy templates so
    # they cannot silently consume the older command proof's layout.inc.
    for name, path in (('core', ROOT / 'bench/window-cache-overlay/core.s'),
                       ('gateway', base.SOURCE / 'gateway.s')):
        (WORK / (name+'.s')).write_text(path.read_text())
    for name in ('core', 'module', 'gateway'):
        path = WORK / (name+'.s')
        subprocess.run(['ca65', '-I', str(SOURCE), '-o', str(WORK / (name+'.o')), str(path)], check=True)
    subprocess.run(['ld65', '-C', str(base.OLD / 'gateway.cfg'), '-o', str(WORK / 'gateway.bin'),
                    str(WORK / 'gateway.o')], check=True)
    for name, path in (('policy', ROOT / 'src/services/window/move_cache_state.c'),
                       ('command', ROOT / 'src/services/window/cache_overlay.c'),
                       ('flow', ROOT / 'src/services/window/move_cache_flow.c'),
                       ('controller', SOURCE / 'controller.c')):
        subprocess.run(['cl65', '-t', 'none', '--cpu', '6502', '-Oirs', '--standard', 'c99',
            '-I', str(ROOT / 'include'), *[x for d in defines for x in ('-D', d)],
            '-c', '-o', str(WORK / (name+'.o')), str(path)], check=True)
    subprocess.run(['cl65', '-t', 'none', '-C', str(SOURCE / 'module.cfg'),
        '-m', str(WORK / 'module.map'), '-o', str(WORK / 'module.bin'),
        *[str(WORK / (n+'.o')) for n in ('core', 'module', 'policy', 'command', 'flow', 'controller')]], check=True)
    image = (WORK / 'module.bin').read_bytes()
    if len(image) > 0x1020:
        raise ValueError('controller reaches private state')
    if image[:213] != (ROOT / 'bench/artifacts/2026-09-28-window-cache-command/build/module.bin').read_bytes()[:213]:
        raise ValueError('qualified row core changed')
    (WORK / 'module-envelope.bin').write_bytes(image.ljust(0x1100, b'\0'))
    driver = (base.OLD / 'driver.s').read_text().replace(', _vic_cache_row_candidate', '')
    start = driver.index('_runtime_row:\n'); end = driver.index('_runtime_check_memory:\n')
    driver = driver[:start] + driver[end:]
    driver = driver.replace(', _runtime_row', '')
    driver = driver.replace('#$0b                ; exact private $4200-$4CFF envelope',
                            '#$11                ; private controller envelope')
    driver = driver.replace('#$13\n', '#$15\n') # 22-byte gap AFTER the four-byte flow
    driver = driver.replace('ROW+9,x', 'FLOW+4,x')
    driver = driver.replace('$f740', '$ff80').replace(
        '$ff80+irq_end-irq <= $f780', '$ff80+irq_end-irq < $fffa')
    driver = driver.replace('module_image_end-module_image = $b00',
                            'module_image_end-module_image = $1100')
    driver = driver.replace('build/bench/window-cache-c-runtime/module-envelope.bin',
                            'build/bench/window-cache-controller/module-envelope.bin')
    driver = driver.replace('.import _private_cache_policy_call',
                            '.import _udeks_nmi_drain\n        .import _private_cache_policy_call')
    driver = driver.replace('mapped:\n        lda $dc0d',
                            'mapped:\n        jsr _udeks_nmi_drain\n        lda $dc0d')
    (WORK / 'driver.s').write_text(driver)
    launcher = (ROOT / 'bench/graphics-raster/launcher.s').read_text().replace(
        '#<$7800', '#<$eff0').replace('#>$7800', '#>$eff0')
    (WORK / 'launcher.s').write_text(launcher)
    binding = (base.SOURCE / 'binding.s').read_text().replace(
        'build/bench/window-cache-command/gateway.bin', 'build/bench/window-cache-controller/gateway.bin')
    (WORK / 'binding.s').write_text(binding)
    for name, path in (('driver', WORK / 'driver.s'), ('launcher', WORK / 'launcher.s'),
                       ('binding', WORK / 'binding.s'), ('nmi', ROOT / 'src/8502/nmi.s'),
                       ('observer', ROOT / 'bench/window-cache-nmi/probe.s')):
        subprocess.run(['ca65', '-I', str(SOURCE), '-I', str(ROOT / 'src/8502'),
            '-o', str(WORK / (name+'.o')), str(path)], check=True)
    for case in (0, 1):
        stem = WORK / f'probe-{case}'
        subprocess.run(['cl65', '-t', 'none', '--standard', 'c99', '-Oirs', '-D', f'CASE={case}',
            '-c', '-o', str(stem.with_suffix('.o')), str(SOURCE / 'probe.c')], check=True)
        subprocess.run(['cl65', '-t', 'none', '-C', str(base.OLD / 'probe.cfg'),
            '-m', str(stem.with_suffix('.map')), '-o', str(stem.with_suffix('.bin')),
            *[str(WORK / (n+'.o')) for n in ('launcher', f'probe-{case}', 'driver', 'binding', 'nmi', 'observer')]], check=True)
        stem.with_suffix('.prg').write_bytes(b'\x00\x20' + stem.with_suffix('.bin').read_bytes())
    normal = (WORK / 'probe-0.prg').read_bytes(); gate = (WORK / 'gateway.bin').read_bytes()
    if normal.count(gate) != 1:
        raise ValueError('ambiguous gateway')
    controls = {}
    for name, pattern, delta, new in (('irq-leak', b'\x08\x78\xd8', 1, 0xea),
            ('zp-leak', b'\x68\x95\x06\xe8', 2, 7),
            ('shell-stack', b'\xa9\x53\x85\x07', 1, 0xef)):
        if gate.count(pattern) != 1:
            raise ValueError('ambiguous fault '+name)
        offset = normal.index(gate) + gate.index(pattern) + delta
        bad = bytearray(normal); old = bad[offset]; bad[offset] = new
        (WORK / f'probe-{name}.prg').write_bytes(bad)
        controls[name] = {'offset': offset, 'before': old, 'after': new}
    stub = bytes.fromhex('48a9018df5ff6840')
    if normal.count(stub) != 1:
        raise ValueError('ambiguous NMI stub')
    offset = normal.index(stub)+3
    bad = bytearray(normal); bad[offset] = 0x2c
    (WORK / 'probe-no-pending.prg').write_bytes(bad)
    controls['no-pending'] = {'offset': offset, 'before': 0x8d, 'after': 0x2c}
    objects, segments = parse_map((WORK / 'module.map').read_text())
    sizes = {n: object_sizes(WORK / (n+'.o')) for n in ('policy', 'command', 'flow', 'controller', 'binding')}
    paths = list(SOURCE.iterdir()) + list(base.SOURCE.iterdir()) + [Path(__file__),
        base.OLD / 'driver.s', base.OLD / 'probe.cfg', base.OLD / 'gateway.cfg',
        ROOT / 'bench/window-cache-overlay/core.s', ROOT / 'bench/graphics-raster/launcher.s',
        ROOT / 'bench/window-cache-nmi/probe.s', ROOT / 'src/8502/nmi.s', ROOT / 'src/8502/nmi-common.inc',
        ROOT / 'tools/window_cache_command.py', ROOT / 'tools/vice_capture.py',
        ROOT / 'tools/1986_raster_bench.c', ROOT / 'tools/1986_input_smoke_build.py',
        ROOT / 'tools/graphics_raster_bench_run.py']
    paths += [ROOT / 'include/udeks' / n for n in ('window_cache_flow.h', 'window_cache_command.h', 'window_cache_state.h')]
    paths += [ROOT / 'src/services/window' / n for n in ('move_cache_flow.c', 'cache_overlay.c', 'move_cache_state.c')]
    paths += [ROOT / 'tests' / n for n in ('test_window_cache_flow.py', 'test_window_cache_controller.py')]
    linked = ('module.bin', 'module-envelope.bin', 'module.map', 'module.s', 'core.s', 'gateway.s', 'gateway.bin', 'driver.s',
        'launcher.s', 'binding.s', 'probe-0.bin', 'probe-0.map', 'probe-1.bin', 'probe-1.map')
    report = {'qualification': 'standalone direct bank-1 controller; GUI moves disabled',
        'module_bytes': len(image), 'module_segments': {n: [s, e] for n, s, e in segments},
        'objects': sizes, 'state': [0x5220, 0x5239], 'private_stack': [0x5250, 0x533f],
        'stack_guard': [0x5340, 0x534f], 'image': [0x5350, 0x5bff], 'image_bytes': 2224,
        'default_image_bytes': 2184, 'image_spare': 40, 'gateway_bytes': len(gate),
        'remaining_resident_padding_before_hooks_delivery': 502 - sizes['binding']['CODE'],
        'defines': defines, 'negative_controls': controls,
        'helpers': sorted(n for n in objects if 'none.lib(' in n),
        'cc65': subprocess.check_output(['cc65', '--version'], stderr=subprocess.STDOUT, text=True).strip(),
        'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in paths if p.is_file()},
        'linked_sha256': {n: digest(WORK / n) for n in linked},
        'program_sha256': {f'probe-{c}.prg': digest(WORK / f'probe-{c}.prg') for c in CASES}}
    (WORK / 'build-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if not k.endswith('sha256')}, indent=2))

def facts(data, case):
    if case not in (0, 1) or len(data) != 8096 or data[:8] != b'CTRL\x01\x02'+bytes((case, 0)):
        raise ValueError('controller header/semantic failure')
    rows, calls, images = (132, 476, 66) if case == 0 else (312, 333, 2)
    if (int.from_bytes(data[8:10], 'little'), int.from_bytes(data[10:12], 'little'), data[14]) != (rows, calls, images):
        raise ValueError('incomplete controller continuations')
    irq = int.from_bytes(data[12:14]+data[24:26], 'little')
    total = int.from_bytes(data[26:30], 'little')
    worker = int.from_bytes(data[30:34], 'little')
    drains = int.from_bytes(data[34:36], 'little')
    if not irq or data[23] != 15 or any(data[36:64]) or data[64:] != base.reference(case):
        raise ValueError('IRQ/flags/guards/reserved/pixel oracle failed')
    return {'rows': rows, 'commands': calls, 'images': images, 'interrupts': irq,
        'nmi_total': total, 'nmi_worker_flat': worker, 'nmi_drains': drains,
        'observed_stack_offset': data[22], 'pixel_sha256': digest_bytes(data[64:])}

def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()

def decode(data, case):
    r = facts(data, case)
    if any(data[15:22]) or not 0x40 <= data[22] < 0xf0:
        raise ValueError('runtime/stack/guard failure')
    if not 0 < r['nmi_worker_flat'] < r['nmi_total'] < 65536 or r['nmi_total'] != r['nmi_drains']:
        raise ValueError('worker/kernel NMI/deferred drain failure')
    return r

def negative(data, name):
    r = facts(data, 0)
    required = {'irq-leak': (15,), 'zp-leak': (16,), 'shell-stack': (19, 21), 'no-pending': ()}[name]
    if any(data[i] != (1 if i in required else 0) for i in range(15, 22)):
        raise ValueError('missing/unexpected fault '+name)
    if name == 'shell-stack':
        if data[22] != 0xf0: raise ValueError('wrong private stack use')
    elif not 0x40 <= data[22] < 0xf0:
        raise ValueError('unexercised private stack')
    if name == 'no-pending':
        if r['nmi_total'] != 1 or r['nmi_drains'] != 0:
            raise ValueError('NMI pending fault not detected')
    elif name != 'irq-leak':
        if not 0 < r['nmi_worker_flat'] < r['nmi_total'] < 65536 or r['nmi_total'] != r['nmi_drains']:
            raise ValueError('unrelated NMI failure')
    try: decode(data, 0)
    except ValueError: pass
    else: raise ValueError('fault passed positive decoder')
    return {**r, 'detected_fields': list(required)}

def verify(report):
    for key, root in (('source_sha256', ROOT), ('linked_sha256', WORK), ('program_sha256', WORK)):
        for n, sha in report[key].items():
            if digest(root / n) != sha: raise ValueError('input drift '+n)

def run(engine, output):
    from graphics_raster_bench_run import emulator_provenance
    r = json.loads((WORK / 'build-report.json').read_text()); verify(r)
    output.mkdir(parents=True, exist_ok=True)
    if engine == '1986':
        emulator = ROOT.parent / '1986'
        sources = importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
        provenance = emulator_provenance(emulator, sources)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'sdl3'], text=True))
        runner = WORK / '1986-controller'
        subprocess.run(['cc', '-std=gnu11', '-O2', '-I'+str(emulator / 'src'),
            str(ROOT / 'tools/1986_raster_bench.c'), *map(str, sources), *flags, '-lm', '-o', str(runner)], check=True)
    elif engine == 'vice':
        provenance = subprocess.check_output(['flatpak', 'info', 'net.sf.VICE'], text=True)
    else: raise ValueError('run requires --engine')
    decoded = {}; raw = {}
    for c in CASES:
        program = WORK / f'probe-{c}.prg'; path = output / f'{engine}-{c}.bin'
        cmd = ([str(runner), str(program), str(path), 'CTRL'] if engine == '1986' else
            ['python3', str(ROOT / 'tools/vice_capture.py'), str(program), str(path),
             '--entry', '0x2000', '--raw-load', '--result-address', '0x7fc0',
             '--result-size', '8096', '--state-offset', '5', '--timeout', '90'])
        subprocess.run(cmd, check=True)
        decoded[str(c)] = decode(path.read_bytes(), c) if isinstance(c, int) else negative(path.read_bytes(), c)
        raw[path.name] = digest(path); print(json.dumps(decoded[str(c)]), flush=True)
    verify(r)
    if engine == '1986' and emulator_provenance(emulator, sources) != provenance:
        raise ValueError('emulator drift')
    (output / f'{engine}-run.json').write_text(json.dumps({'program_sha256': r['program_sha256'],
        'raw_sha256': raw, 'decoded': decoded, 'provenance': provenance}, indent=2)+'\n')

def preserve(output):
    r = json.loads((WORK / 'build-report.json').read_text()); verify(r)
    for engine in ('1986', 'vice'):
        run_record = json.loads((output / f'{engine}-run.json').read_text())
        if run_record['program_sha256'] != r['program_sha256']:
            raise ValueError('run/program mismatch')
        if set(run_record['raw_sha256']) != {f'{engine}-{c}.bin' for c in CASES}:
            raise ValueError('missing run')
        for n, sha in run_record['raw_sha256'].items():
            if digest(output / n) != sha: raise ValueError('raw drift')
        for c in CASES:
            data = (output / f'{engine}-{c}.bin').read_bytes()
            value = decode(data, c) if isinstance(c, int) else negative(data, c)
            if value != run_record['decoded'][str(c)]: raise ValueError('decoded drift')
    artifacts = ROOT / 'bench/artifacts' / NAME; results = ROOT / 'bench/results' / NAME
    if artifacts.exists() or results.exists(): raise ValueError('refusing to overwrite evidence')
    artifacts.mkdir(parents=True); results.mkdir(parents=True)
    for n in r['source_sha256']:
        dest = artifacts / n; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / n, dest)
    for n in set(r['linked_sha256']) | set(r['program_sha256']) | {'build-report.json'}:
        dest = artifacts / 'build' / n; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(WORK / n, dest)
    for p in output.iterdir():
        if p.suffix in ('.bin', '.json'): shutil.copy2(p, results / p.name)
    for directory in (artifacts, results):
        paths = sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('build', 'run', 'preserve'))
    p.add_argument('--engine', choices=('1986', 'vice'))
    p.add_argument('--output', type=Path, default=ROOT / 'build/bench/window-cache-controller-results')
    a = p.parse_args()
    if a.action == 'build': build()
    elif a.action == 'run': run(a.engine, a.output)
    else: preserve(a.output)

if __name__ == '__main__': main()

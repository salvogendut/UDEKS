#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify an isolated C-clipping/ASM-span fill, never a production disk."""
import argparse
import hashlib
import importlib
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from graphics_raster_bench_build import ROOT, REFERENCE_SOURCE, function
from graphics_raster_bench_decode import decode, reference
from graphics_raster_link_audit import reference_link_command, reference_segments, segments
from graphics_raster_bench_run import emulator_provenance
from gen_capability_imports import map_exports
from placement_audit import parse_map

NAME = '2026-09-28-graphics-span'
CASES = (2, 3, 4, 5)
VARIANTS = ('c-reference', 'asm-span')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_fill(source):
    old = function(source, 'udeks_vic_bitmap_fill').rstrip()
    if source.count(old) != 1:
        raise ValueError('ambiguous fill replacement')
    return source.replace(old, (ROOT / 'bench/graphics-span/fill.c').read_text())


def object_sizes(path):
    dump = subprocess.check_output(['od65', '--dump-segments', str(path)], text=True)
    return {name: int(size) for name, size in re.findall(
        r'Name:\s*"([^"]+)"\s+Flags:\s*\d+\s+Size:\s*(\d+)', dump)}


def build(work):
    work.mkdir(parents=True, exist_ok=True)
    source = REFERENCE_SOURCE.read_text()
    report = {'qualification': 'standalone fill mechanism; not resident or live-input qualified',
              'flags': {'display': '-Oirs', 'driver': 'unoptimized'},
              'cc65': subprocess.check_output(['cc65', '--version'], text=True, stderr=subprocess.STDOUT).strip()}
    common = ['-t', 'none', '--cpu', '6502', '--standard', 'c99', '-I', str(ROOT / 'include')]
    subprocess.run(['ca65', '--cpu', '6502', '-o', str(work / 'span.o'),
                    str(ROOT / 'bench/graphics-span/span.s')], check=True)
    subprocess.run(['ca65', '--cpu', '6502', '-o', str(work / 'launcher.o'),
                    str(ROOT / 'bench/graphics-raster/launcher.s')], check=True)
    for variant, label in enumerate(VARIANTS):
        full = work / f'{label}-full.c'
        full.write_text(source if variant == 0 else replace_fill(source))
        subprocess.run(['cl65', *common, '-Oirs', '-c', '-o', str(full.with_suffix('.o')), str(full)], check=True)
        report[label] = object_sizes(full.with_suffix('.o'))
        unit = work / f'{label}.c'
        prefix = source.split('static void increment_counter(', 1)[0]
        fragment = (function(source, 'udeks_vic_bitmap_fill') if variant == 0
                    else (ROOT / 'bench/graphics-span/fill.c').read_text())
        unit.write_text(prefix + fragment)
        subprocess.run(['cl65', *common, '-Oirs', '-c', '-o', str(unit.with_suffix('.o')), str(unit)], check=True)
        for case in CASES:
            stem = work / f'{label}-{case}'
            driver = ROOT / ('bench/graphics-span/matrix.c' if case >= 4 else 'bench/graphics-raster/workload.c')
            subprocess.run(['cl65', *common, '-D', f'VARIANT={variant}', '-D', f'CASE={case}',
                            '-c', '-o', str(stem.with_suffix('.o')), str(driver)], check=True)
            subprocess.run(['cl65', '-t', 'none', '--cpu', '6502', '-C', str(ROOT / 'cfg/8502-raster-bench.cfg'),
                            '-m', str(stem.with_suffix('.map')), '-o', str(stem.with_suffix('.bin')),
                            str(work / 'launcher.o'), str(stem.with_suffix('.o')), str(unit.with_suffix('.o')),
                            *([str(work / 'span.o')] if variant else [])], check=True)
            stem.with_suffix('.prg').write_bytes(b'\x00\x20' + stem.with_suffix('.bin').read_bytes())
    report['span'] = object_sizes(work / 'span.o')
    report['object_net_saving'] = sum(report['c-reference'][name] - report['asm-span'][name] -
                                      report['span'][name] for name in ('CODE', 'BSS'))
    # Retarget all linker side outputs, not just the main experimental image.
    command = reference_link_command(work)
    link_maps = {}
    linked_modules = {}
    for label in VARIANTS:
        directory = work / f'link-{label}'; directory.mkdir(exist_ok=True)
        cfg = re.sub(r'file = "(build/[^"\n]+)"',
                     lambda m: 'file = "' + str(directory / Path(m[1]).name) + '"',
                     (ROOT / 'cfg/8502-bootstrap.cfg').read_text())
        cfg_path = directory / 'kernel.cfg'; cfg_path.write_text(cfg)
        local = command[:]
        local[local.index('-C') + 1] = str(cfg_path)
        local[local.index('-m') + 1] = str(directory / 'kernel.map')
        local[local.index('-o') + 1] = str(directory / 'kernel.bin')
        local[local.index('build/8502/vic_graphics.o')] = str(work / f'{label}-full.o')
        if label == 'asm-span': local.append(str(work / 'span.o'))
        subprocess.run(local, cwd=ROOT, check=True)
        link_maps[label] = segments((directory / 'kernel.map').read_text())
        linked_modules[label] = sorted(name for name in parse_map((directory / 'kernel.map').read_text())[0]
                                        if 'none.lib(' in name)
    if link_maps['c-reference'] != reference_segments():
        raise ValueError('experimental baseline and preserved reference map differ')
    report['experimental_link'] = link_maps
    report['linked_helpers'] = linked_modules
    report['linked_net_saving'] = link_maps['c-reference']['BSS']['end'] - link_maps['asm-span']['BSS']['end']
    report['program_sha256'] = {f'{label}-{case}.prg': digest(work / f'{label}-{case}.prg')
                                for label in VARIANTS for case in CASES}
    paths = [ROOT / path for path in ('src/services/display/vic_graphics.c', 'bench/graphics-raster/launcher.s',
             'bench/graphics-raster/workload.c', 'cfg/8502-raster-bench.cfg', 'cfg/8502-bootstrap.cfg',
             'tools/1986_raster_bench.c', 'tools/1986_input_smoke_build.py', 'tools/vice_capture.py',
             'tools/graphics_raster_bench_build.py', 'tools/graphics_raster_bench_decode.py',
             'tools/graphics_raster_link_audit.py', 'tools/graphics_raster_bench_run.py',
             'tools/graphics_raster_audit.py', 'tools/gen_capability_imports.py', 'tools/placement_audit.py',
             'Makefile', 'build/8502/udeks-8502.map')]
    paths += list((ROOT / 'bench/graphics-span').iterdir()) + list((ROOT / 'include/udeks').glob('*.h')) + [Path(__file__)]
    paths += [REFERENCE_SOURCE, ROOT / 'src/8502/vic_graphics.s']
    report['source_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths) if path.is_file()}
    (work / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({name: report[name] for name in ('c-reference', 'asm-span', 'span',
                                                    'object_net_saving', 'linked_net_saving')}, indent=2))


def matrix_operations():
    result = [(a, color*64+a*8+b, 17+b-a, 1, color)
              for color in range(2) for a in range(8) for b in range(8)]
    for a in range(8):
        for width in range(1, 9-a):
            result.extend([(a, 128+a*8+width-1, width, 1, 0),
                           (312+a, 128+a*8+width-1, width, 1, 7)])
    return result + [(0,192,320,1,0), (0,193,320,1,255), (319,199,1,1,0), (0,198,1,1,7),
                     (-3,-2,12,5,0), (318,198,10,10,7), (10,10,0,10,0), (10,10,10,-1,0),
                     (320,0,10,10,0), (0,200,10,10,0)]


def matrix_reference(case=4):
    bitmap = bytearray((i*13+7) & 255 for i in range(8000)); dirty = bytearray(32)
    operations = matrix_operations() if case == 4 else [(0,6,320,1,0)]
    for x, y, width, height, color in operations:
        if width <= 0 or height <= 0: continue
        for yy in range(max(0, y), min(200, y+height)):
            for xx in range(max(0, x), min(320, x+width)):
                offset = (yy//8)*320 + (xx//8)*8 + yy%8
                mask = 128 >> (xx%8)
                bitmap[offset] = (bitmap[offset] | mask) if color == 0 else (bitmap[offset] & ~mask)
                dirty[offset//256] = 1
    return bytes(bitmap + dirty)


def decode_span(data, variant, case):
    if case in (2, 3): return decode(data, variant, case)
    if case not in (4, 5): raise ValueError('unknown span case')
    if len(data) != 8096 or data[:8] != b'RAST\x01\x02' + bytes((variant, case)):
        raise ValueError('bad span matrix record')
    if data[12:15] != b'\x5a\xa5\xc3' or any(data[15:64]):
        raise ValueError('span guard/reserved bytes failure')
    elapsed = int.from_bytes(data[8:12], 'little')
    if not elapsed or data[64:] != matrix_reference(case):
        raise ValueError('span timer/pixel/dirty failure')
    return elapsed


def run(args):
    report = json.loads((args.work / 'build-report.json').read_text())
    for name, sha in report['source_sha256'].items():
        if digest(ROOT / name) != sha: raise ValueError('source drift; rebuild')
    for name, sha in report['program_sha256'].items():
        if digest(args.work / name) != sha: raise ValueError('program drift; rebuild')
    args.output.mkdir(parents=True, exist_ok=True)
    if args.engine == '1986':
        sources = importlib.import_module('1986_input_smoke_build').emulator_sources(args.emulator)
        before = emulator_provenance(args.emulator, sources)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'sdl3'], text=True))
        runner = args.work / '1986-span-bench'
        subprocess.run(['cc', '-std=gnu11', '-O2', '-I' + str(args.emulator / 'src'),
                        str(ROOT / 'tools/1986_raster_bench.c'), *map(str, sources),
                        *flags, '-lm', '-o', str(runner)], check=True)
    for variant, label in enumerate(VARIANTS):
        for case in CASES:
            name = f'{label}-{case}.prg'; program = args.work / name
            if digest(program) != report['program_sha256'][name]: raise ValueError('program changed during run')
            raw = args.output / f'{args.engine}-{label}-{case}.bin'
            command = ([str(runner), str(program), str(raw)] if args.engine == '1986' else
                       ['python3', str(ROOT / 'tools/vice_capture.py'), str(program), str(raw),
                        '--entry', '0x2000', '--result-address', '0x7fc0', '--result-size', '8096',
                        '--state-offset', '5', '--raw-load', '--timeout', '90'])
            subprocess.run(command, check=True)
            print(f'{args.engine} {label} {case}: {decode_span(raw.read_bytes(), variant, case)} ticks', flush=True)
    for name, sha in report['source_sha256'].items():
        if digest(ROOT / name) != sha: raise ValueError('source changed during run')
    for name, sha in report['program_sha256'].items():
        if digest(args.work / name) != sha: raise ValueError('program changed during run')
    if args.engine == '1986':
        if before != emulator_provenance(args.emulator, sources): raise ValueError('emulator inputs changed')
        (args.output / '1986-provenance.json').write_text(json.dumps(before, indent=2) + '\n')
    else:
        (args.output / 'VICE-flatpak.txt').write_text(subprocess.check_output(['flatpak', 'info', 'net.sf.VICE'], text=True))
    (args.output / f'{args.engine}-run.json').write_text(json.dumps({
        'program_sha256': report['program_sha256'],
        'raw_sha256': {f'{args.engine}-{label}-{case}.bin': digest(args.output / f'{args.engine}-{label}-{case}.bin')
                       for label in VARIANTS for case in CASES}}, indent=2) + '\n')


def compare(output):
    report = {'qualification': 'IRQs masked, display off, 1 MHz; no compositor/commit/input claim', 'cases': []}
    for case in CASES:
        row = {'case': case}
        for engine in ('1986', 'vice'):
            counts = [decode_span((output / f'{engine}-{label}-{case}.bin').read_bytes(), variant, case)
                      for variant, label in enumerate(VARIANTS)]
            row[engine] = {'c_ticks': counts[0], 'asm_ticks': counts[1],
                           'speedup': round(counts[0]/counts[1], 4)}
        report['cases'].append(row)
    return report


def validate_fault(data):
    # Pixels must still match exactly. Only logical page zero's missing flag
    # should cause rejection. Restoring that one byte must make the strict
    # decoder pass, proving this is a dirty-map negative control.
    expected = matrix_reference(5)
    if data[64:8064] != expected[:8000] or data[8064:] != b'\x00\x01' + bytes(30):
        raise ValueError('fault did not isolate the initial dirty flag')
    try:
        decode_span(data, 1, 5)
    except ValueError:
        repaired = bytearray(data); repaired[8064] = 1
        decode_span(repaired, 1, 5)
    else:
        raise ValueError('dirty fault unexpectedly passed')


def fault(args):
    report = json.loads((args.work / 'build-report.json').read_text())
    original = args.work / 'asm-span-5.prg'
    if digest(original) != report['program_sha256'][original.name]: raise ValueError('fault base PRG drift')
    data = bytearray(original.read_bytes())
    entry = map_exports((args.work / 'asm-span-5.map').read_text())['_udeks_span_fill_row'][0]
    offset = entry - 0x2000 + 2
    code = data[offset:offset+report['span']['CODE']]
    stores = [i for i in range(len(code)-2) if code[i:i+3] == b'\x99\x90\xe1']
    if len(stores) != 2: raise ValueError('expected initial and crossing dirty stores')
    patch = offset + stores[0]; data[patch:patch+3] = b'\xea\xea\xea'
    program = args.work / 'negative-dirty.prg'; program.write_bytes(data)
    metadata = {'base_sha256': digest(original), 'fault_sha256': digest(program),
                'file_offset': patch, 'before': '9990e1', 'after': 'eaeaea'}
    (args.work / 'negative-dirty.json').write_text(json.dumps(metadata, indent=2) + '\n')
    raw = args.output / f'{args.engine}-negative-dirty.bin'
    if args.engine == '1986':
        command = [str(args.work / '1986-span-bench'), str(program), str(raw)]
    else:
        command = ['python3', str(ROOT / 'tools/vice_capture.py'), str(program), str(raw),
                   '--entry', '0x2000', '--result-address', '0x7fc0', '--result-size', '8096',
                   '--state-offset', '5', '--raw-load', '--timeout', '90']
    subprocess.run(command, check=True)
    validate_fault(raw.read_bytes())
    (args.output / f'{args.engine}-fault.json').write_text(json.dumps({
        'program_sha256': digest(program), 'raw_sha256': digest(raw)}, indent=2) + '\n')
    print(f'{args.engine}: missing initial dirty flag rejected, pixels unchanged')


def preserve(args):
    artifacts = ROOT / 'bench/artifacts' / NAME; results = ROOT / 'bench/results' / NAME
    if artifacts.exists() or results.exists(): raise ValueError('refusing to overwrite preserved evidence')
    build_report = json.loads((args.work / 'build-report.json').read_text())
    for name, sha in build_report['source_sha256'].items():
        if digest(ROOT / name) != sha: raise ValueError('source changed since qualification')
    for name, sha in build_report['program_sha256'].items():
        if digest(args.work / name) != sha: raise ValueError('PRG changed since qualification')
    report = compare(args.output)
    for engine in ('1986', 'vice'):
        manifest = json.loads((args.output / f'{engine}-run.json').read_text())
        if manifest['program_sha256'] != build_report['program_sha256']: raise ValueError('run bound to another build')
        expected = {f'{engine}-{label}-{case}.bin' for label in VARIANTS for case in CASES}
        if set(manifest['raw_sha256']) != expected: raise ValueError('incomplete raw manifest')
        for name, sha in manifest['raw_sha256'].items():
            if digest(args.output / name) != sha: raise ValueError('raw record changed since run')
        validate_fault((args.output / f'{engine}-negative-dirty.bin').read_bytes())
        fault_manifest = json.loads((args.output / f'{engine}-fault.json').read_text())
        if fault_manifest != {'program_sha256': digest(args.work / 'negative-dirty.prg'),
                              'raw_sha256': digest(args.output / f'{engine}-negative-dirty.bin')}:
            raise ValueError('fault record is not bound to its exact PRG')
    artifacts.mkdir(parents=True); results.mkdir(parents=True)
    for path in args.work.rglob('*'):
        if path.is_file() and path.suffix in ('.prg', '.map', '.s', '.c', '.cfg', '.json'):
            target = artifacts / 'build' / path.relative_to(args.work)
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
    for name in build_report['source_sha256']:
        target = artifacts / 'sources' / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    for path in args.output.iterdir():
        if path.is_file(): shutil.copyfile(path, results / path.name)
    (results / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    for directory in (artifacts, results):
        (directory / 'SHA256SUMS').write_text(''.join(digest(path) + '  ' + str(path.relative_to(directory)) + '\n'
                 for path in sorted(directory.rglob('*')) if path.is_file() and path.name != 'SHA256SUMS'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'run', 'decode', 'fault', 'preserve'))
    parser.add_argument('--work', type=Path, default=ROOT / 'build/graphics-span')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/graphics-span-results')
    parser.add_argument('--engine', choices=('1986', 'vice'))
    parser.add_argument('--emulator', type=Path, default=ROOT.parent / '1986')
    args = parser.parse_args()
    if args.action == 'build': build(args.work)
    elif args.action in ('run', 'fault'):
        if args.engine is None: parser.error('--engine required')
        (run if args.action == 'run' else fault)(args)
    elif args.action == 'decode': print(json.dumps(compare(args.output), indent=2))
    else: preserve(args)


if __name__ == '__main__': main()

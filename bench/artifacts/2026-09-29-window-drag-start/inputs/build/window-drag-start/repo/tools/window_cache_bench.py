#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build/run/decode the standalone bank-crossing window-cache prototype.

Never builds or patches a resident UDEKS disk. Native builds require SDL in
my-distrobox; VICE runs use the deterministic paused-monitor raw loader.
"""
import argparse
import hashlib
import importlib
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_NAME = '2026-09-28-window-cache-transfer'
ASM_EVIDENCE_NAME = '2026-09-28-window-cache-asm'


def sizes(path):
    dump = subprocess.check_output(['od65', '--dump-segments', str(path)], text=True)
    return {name: int(size) for name, size in re.findall(
        r'Name:\s*"([^"]+)"\s+Flags:\s*\d+\s+Size:\s*(\d+)', dump)}


def build(work, variant='c'):
    work.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'bench/window-cache'
    common = ['-t', 'none', '--cpu', '6502', '--standard', 'c99', '-I', str(source)]
    cache_source = source / ('cache-fast.c' if variant == 'asm' else 'cache.c')
    subprocess.run(['cc65', *common, '-Oirs', '-o', str(work / 'cache.s'), str(cache_source)], check=True)
    subprocess.run(['ca65', '--cpu', '6502', '-o', str(work / 'cache.o'), str(work / 'cache.s')], check=True)
    assemblies = [('launcher', ROOT / 'bench/graphics-raster/launcher.s'),
                  ('transfer', source / ('transfer-lease.s' if variant == 'asm' else 'transfer.s'))]
    if variant == 'asm': assemblies.append(('rows', source / 'rows.s'))
    for name, path in assemblies:
        subprocess.run(['ca65', '--cpu', '6502', '-o', str(work / f'{name}.o'), str(path)], check=True)
    for case in range(11):
        stem = work / f'cache-{case}'
        subprocess.run(['cc65', *common, '-D', f'CASE={case}', '-o', str(stem) + '.s', str(source / 'probe.c')], check=True)
        subprocess.run(['ca65', '--cpu', '6502', '-o', str(stem) + '.o', str(stem) + '.s'], check=True)
        subprocess.run(['cl65', '-t', 'none', '--cpu', '6502', '-C', str(ROOT / 'cfg/8502-raster-bench.cfg'),
                        '-m', str(stem) + '.map', '-o', str(stem) + '.bin',
                        str(work / 'launcher.o'), str(stem) + '.o', str(work / 'cache.o'),
                        str(work / 'transfer.o'),
                        *([str(work / 'rows.o')] if variant == 'asm' else [])], check=True)
        subprocess.run(['python3', str(ROOT / 'tools/bin_to_prg.py'), '--load-address', '0x2000',
                        str(stem) + '.bin', str(stem) + '.prg'], check=True)
    if variant == 'asm':
        stem = work / 'cache-matrix'
        subprocess.run(['cc65', *common, '-o', str(stem) + '.s', str(source / 'row-probe.c')], check=True)
        subprocess.run(['ca65', '--cpu', '6502', '-o', str(stem) + '.o', str(stem) + '.s'], check=True)
        subprocess.run(['cl65', '-t', 'none', '--cpu', '6502', '-C', str(ROOT / 'cfg/8502-raster-bench.cfg'),
                        '-m', str(stem) + '.map', '-o', str(stem) + '.bin',
                        str(work / 'launcher.o'), str(stem) + '.o', str(work / 'cache.o'),
                        str(work / 'transfer.o'), str(work / 'rows.o')], check=True)
        subprocess.run(['python3', str(ROOT / 'tools/bin_to_prg.py'), '--load-address', '0x2000',
                        str(stem) + '.bin', str(stem) + '.prg'], check=True)
    report = {'variant': variant,
              'qualification': 'standalone prototype; no resident placement or active IRQ qualification',
              'flags': {'cache': '-Oirs', 'driver': 'unoptimized (avoids const-pointer store optimizer defect)'},
              'cc65': subprocess.check_output(['cc65', '--version'], text=True, stderr=subprocess.STDOUT).strip(),
              'cache_object': sizes(work / 'cache.o'), 'transfer_object': sizes(work / 'transfer.o'),
              'sources_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in sorted(list(source.iterdir()) + [
                                      ROOT / 'bench/graphics-raster/launcher.s',
                                      ROOT / 'cfg/8502-raster-bench.cfg',
                                      ROOT / 'tools/bin_to_prg.py',
                                      Path(__file__), ROOT / 'tools/1986_raster_bench.c',
                                      ROOT / 'tools/1986_input_smoke_build.py',
                                      ROOT / 'tools/graphics_raster_bench_run.py',
                                      ROOT / 'tools/vice_capture.py',
                                      ROOT / 'tools/snapshot_extract.py']) if path.is_file()},
              'program_sha256': {f'cache-{case}.prg': hashlib.sha256(
                  (work / f'cache-{case}.prg').read_bytes()).hexdigest() for case in range(11)}}
    exports = subprocess.check_output(['od65', '--dump-exports', str(work / 'transfer.o')], text=True)
    gateway = re.search(r'Name:\s*"_cache_gateway_size".*?Value:\s*0x([0-9A-Fa-f]+)', exports, re.S)
    if gateway is None:
        raise ValueError('missing measured cache gateway size')
    report['gateway'] = {'size': int(gateway[1], 16), 'run': 0xF68A,
                         'end_inclusive': 0xF68A + int(gateway[1], 16) - 1}
    if variant == 'asm': report['rows_object'] = sizes(work / 'rows.o')
    if variant == 'asm': report['program_sha256']['cache-matrix.prg'] = hashlib.sha256(
        (work / 'cache-matrix.prg').read_bytes()).hexdigest()
    (work / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    report = json.loads((args.work / 'build-report.json').read_text())
    if report.get('variant', 'c') != args.variant:
        raise ValueError('wrong implementation variant; rebuild or select the matching work directory')
    for name, digest in report['program_sha256'].items():
        if hashlib.sha256((args.work / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'{name}: build report mismatch; rebuild before running')
    if args.engine == '1986':
        from graphics_raster_bench_run import emulator_provenance
        sources = importlib.import_module('1986_input_smoke_build').emulator_sources(args.emulator)
        before = emulator_provenance(args.emulator, sources)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'sdl3'], text=True))
        runner = args.work / '1986-cache-bench'
        subprocess.run(['cc', '-std=gnu11', '-O2', '-I' + str(args.emulator / 'src'),
                        str(ROOT / 'tools/1986_raster_bench.c'), *map(str, sources),
                        *flags, '-lm', '-o', str(runner)], check=True)
    cases = list(range(11)) + (['matrix'] if args.variant == 'asm' else [])
    for case in cases:
        program = args.work / f'cache-{case}.prg'
        if hashlib.sha256(program.read_bytes()).hexdigest() != report['program_sha256'][program.name]:
            raise ValueError(f'{program.name}: program changed during the run; restart qualification')
        output = args.output / f'{args.engine}-{case}.bin'
        if args.engine == '1986':
            command = [str(runner), str(program), str(output), 'WROW' if case == 'matrix' else 'WCAC']
        else:
            command = ['python3', str(ROOT / 'tools/vice_capture.py'), str(program), str(output),
                       '--entry', '0x2000', '--result-address', '0x7fc0', '--result-size', '8096',
                       '--state-offset', '5', '--raw-load', '--timeout', '90']
        print(f'{args.engine}: cache alignment {case}', flush=True)
        subprocess.run(command, check=True)
    for name, digest in report['program_sha256'].items():
        if hashlib.sha256((args.work / name).read_bytes()).hexdigest() != digest:
            raise ValueError('program changed during the run; restart qualification')
    if args.engine == '1986':
        after = emulator_provenance(args.emulator, sources)
        if before != after:
            raise RuntimeError('emulator source changed during probe; rerun required')
        (args.output / '1986-provenance.json').write_text(json.dumps(before, indent=2) + '\n')
    (args.output / f'{args.engine}-run.json').write_text(json.dumps({
        'variant': args.variant, 'program_sha256': report['program_sha256'],
        'raw_sha256': {f'{args.engine}-{case}.bin': hashlib.sha256(
            (args.output / f'{args.engine}-{case}.bin').read_bytes()).hexdigest() for case in cases}
    }, indent=2) + '\n')


def reference(case):
    # Independent per-pixel construction, not the prototype's shifted-byte path.
    bitmap = bytearray((offset * 31 + 19) & 255 for offset in range(8000))
    dirty = bytearray(32)
    if case < 8:
        x, y, xx, yy, width, height = 8 + case, 16 + case, 119 - case, 80 + case, 168, 104
    else:
        x, y, xx, yy, width, height = {8: (303, 189, 0, 0, 17, 11),
                                    9: (319, 199, 319, 199, 1, 1),
                                    10: (7, 7, 100, 40, 220, 160)}[case]
    for row in range(height):
        for column in range(width):
            sx, sy = x + column, y + row
            tx, ty = xx + column, yy + row
            source = sy // 8 * 320 + sx // 8 * 8 + sy % 8
            target = ty // 8 * 320 + tx // 8 * 8 + ty % 8
            mask = 128 >> (tx % 8)
            if ((source * 13 + 7) & 255) & (128 >> (sx % 8)):
                bitmap[target] |= mask
            else:
                bitmap[target] &= ~mask & 255
            dirty[target >> 8] = 1
    return bytes(bitmap + dirty)


def decode_record(data, case):
    if len(data) != 8096 or data[:8] != b'WCAC\x01\x02' + bytes((case, 0)):
        raise ValueError('incomplete/failing cache record')
    if data[12:18] != b'\x5a\xa5\x3e\x01\x01\xc3' or any(data[26:64]):
        raise ValueError('guard, mapping, service restore or validation failure')
    capture = int.from_bytes(data[18:22], 'little')
    paste = int.from_bytes(data[22:26], 'little')
    if not capture or not paste or data[8:12] != data[22:26]:
        raise ValueError('invalid timer record')
    if data[64:] != reference(case):
        raise ValueError('bitmap/dirty mismatch')
    return {'capture_ticks': capture, 'paste_ticks': paste, 'total_ticks': capture + paste}


def decode(directory):
    report = {'qualification': 'display disabled, IRQ masked, 1 MHz; isolated capture/paste CIA timer ticks, no GUI latency claim',
              'cases': []}
    for case in range(11):
        row = {'alignment': case}
        for engine in ('1986', 'vice'):
            data = (directory / f'{engine}-{case}.bin').read_bytes()
            try:
                row[engine] = decode_record(data, case)
            except ValueError as error:
                raise ValueError(f'{engine}-{case}: {error}') from error
        row['pixels_dirty_sha256'] = hashlib.sha256(reference(case)).hexdigest()
        report['cases'].append(row)
    return report


def matrix_reference():
    original = bytes((offset * 13 + 7) & 255 for offset in range(8000))
    bitmap = bytearray(original)
    dirty = bytearray(32)
    cases = [(sa, 128, da, sa * 8 + da, 17) for sa in range(8) for da in range(8)]
    cases += [(0, 129, 0, 64, 320), (319, 199, 319, 199, 1)]
    for x, y, xx, yy, width in cases:
        for column in range(width):
            sx, tx = x + column, xx + column
            source = y // 8 * 320 + sx // 8 * 8 + y % 8
            target = yy // 8 * 320 + tx // 8 * 8 + yy % 8
            mask = 128 >> (tx % 8)
            if original[source] & (128 >> (sx % 8)): bitmap[target] |= mask
            else: bitmap[target] &= ~mask & 255
            dirty[target >> 8] = 1
    return bytes(bitmap + dirty)


def decode_matrix(data):
    if (len(data) != 8096 or data[:8] != b'WROW\x01\x02\x00\x00' or
            data[8:14] != b'\x42\x00\x00\x00\x5a\xa5' or any(data[14:64])):
        raise ValueError('incomplete/failing row-matrix record or guard')
    if data[64:] != matrix_reference():
        raise ValueError('row matrix bitmap/dirty mismatch')
    return {'checks': 66, 'pixels_dirty_sha256': hashlib.sha256(data[64:]).hexdigest()}


def validate_run_report(run_report, build_report, output, engine):
    cases = list(range(11)) + (['matrix'] if build_report['variant'] == 'asm' else [])
    if (run_report['variant'] != build_report['variant'] or
            run_report['program_sha256'] != build_report['program_sha256']):
        raise ValueError(f'{engine}: raw records are from a different build')
    if (set(build_report['program_sha256']) != {f'cache-{case}.prg' for case in cases} or
            set(run_report['raw_sha256']) != {f'{engine}-{case}.bin' for case in cases}):
        raise ValueError(f'{engine}: incomplete program/record provenance')
    for name, digest in run_report['raw_sha256'].items():
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'{name}: record changed since qualification')


def preserve(work, output):
    """Generate reproducibility evidence only after all raw records validate."""
    report = decode(output)
    build_report = json.loads((work / 'build-report.json').read_text())
    if build_report['variant'] == 'asm':
        report['matrix'] = {engine: decode_matrix((output / f'{engine}-matrix.bin').read_bytes())
                            for engine in ('1986', 'vice')}
    for engine in ('1986', 'vice'):
        run_report = json.loads((output / f'{engine}-run.json').read_text())
        validate_run_report(run_report, build_report, output, engine)
    for name, digest in build_report['sources_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'{name}: source changed since build')
    for name, digest in build_report['program_sha256'].items():
        if hashlib.sha256((work / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'{name}: binary changed since build')
    evidence_name = ASM_EVIDENCE_NAME if build_report['variant'] == 'asm' else EVIDENCE_NAME
    artifacts = ROOT / 'bench/artifacts' / evidence_name
    results = ROOT / 'bench/results' / evidence_name
    artifacts.mkdir(parents=True, exist_ok=True)
    (results / 'raw').mkdir(parents=True, exist_ok=True)
    for pattern in ('*.prg', '*.map', '*.s', 'build-report.json'):
        for path in work.glob(pattern):
            shutil.copy2(path, artifacts / path.name)
    for name in build_report['sources_sha256']:
        target = artifacts / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    for engine in ('1986', 'vice'):
        for case in list(range(11)) + (['matrix'] if build_report['variant'] == 'asm' else []):
            path = output / f'{engine}-{case}.bin'
            shutil.copy2(path, results / 'raw' / path.name)
        shutil.copy2(output / f'{engine}-run.json', results / f'{engine}-run.json')
    shutil.copy2(output / '1986-provenance.json', results / '1986-provenance.json')
    vice = subprocess.check_output(['flatpak', 'info', 'net.sf.VICE'], text=True)
    (results / 'VICE-flatpak.txt').write_text(vice)
    (results / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    for directory in (artifacts, results):
        entries = [hashlib.sha256(path.read_bytes()).hexdigest() + '  ' +
                   str(path.relative_to(directory)) for path in sorted(directory.rglob('*'))
                   if path.is_file() and path.name not in ('SHA256SUMS', 'README.md')]
        (directory / 'SHA256SUMS').write_text('\n'.join(entries) + '\n')
    print(f'Preserved qualified standalone evidence under {evidence_name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'run', 'decode', 'preserve'))
    parser.add_argument('--variant', choices=('c', 'asm'), default='c')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--engine', choices=('1986', 'vice'))
    parser.add_argument('--emulator', type=Path, default=ROOT.parent / '1986')
    args = parser.parse_args()
    if args.work is None:
        args.work = ROOT / ('build/window-cache-asm' if args.variant == 'asm' else 'build/window-cache-bench')
    if args.output is None:
        args.output = ROOT / ('build/window-cache-asm-results' if args.variant == 'asm' else 'build/window-cache-results')
    if args.action == 'build': build(args.work, args.variant)
    elif args.action == 'run':
        if not args.engine: parser.error('run requires --engine')
        run(args)
    elif args.action == 'decode':
        report = decode(args.output)
        if args.variant == 'asm': report['matrix'] = {
            engine: decode_matrix((args.output / f'{engine}-matrix.bin').read_bytes())
            for engine in ('1986', 'vice')}
        print(json.dumps(report, indent=2))
    else: preserve(args.work, args.output)


if __name__ == '__main__':
    main()

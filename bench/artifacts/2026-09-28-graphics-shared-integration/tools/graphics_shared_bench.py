#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure isolated shared-pixel line, span rectangle and ASM clear candidates."""
import argparse
import importlib
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from graphics_span_bench import ROOT, object_sizes, digest
from graphics_raster_bench_build import function
from graphics_raster_link_audit import link_command, segments
from graphics_raster_bench_run import emulator_provenance
from placement_audit import parse_map

NAME = '2026-09-28-graphics-shared'
LABELS = ('reference', 'combined')


def variant(source, parts):
    for name in parts:
        old = function(source, 'udeks_vic_bitmap_' + name).rstrip()
        new = ('/* Clear supplied by the private ASM candidate. */' if name == 'clear'
               else (ROOT / 'bench/graphics-shared' / (name + '.c')).read_text())
        if source.count(old) != 1:
            raise ValueError('ambiguous raster entry')
        source = source.replace(old, new)
    return source


def build(work):
    work.mkdir(parents=True, exist_ok=True)
    # Immutable installed span/pixel checkpoint, before this shared-raster
    # candidate. Do not silently benchmark the replacement against itself.
    reference_source = ROOT / 'bench/artifacts/2026-09-28-graphics-primitives-integration/src/services/display/vic_graphics.c'
    source = reference_source.read_text()
    report = {'qualification': 'object measurement only; no production changes'}
    common = ['-t', 'none', '--cpu', '6502', '--standard', 'c99', '-I', str(ROOT / 'include')]
    subprocess.run(['ca65', '--cpu', '6502', '-o', str(work / 'clear-mechanism.o'),
                    str(ROOT / 'bench/graphics-shared/clear.s')], check=True)
    clear = object_sizes(work / 'clear-mechanism.o')
    for label, parts in (('reference', ()), ('line', ('line',)),
                        ('rectangle', ('rectangle',)), ('clear', ('clear',)),
                        ('combined', ('line', 'rectangle', 'clear'))):
        path = work / (label + '.c')
        path.write_text(variant(source, parts))
        subprocess.run(['cl65', *common, '-Oirs', '-c', '-o', str(path.with_suffix('.o')), str(path)], check=True)
        report[label] = object_sizes(path.with_suffix('.o'))
        if label != 'reference':
            report[label]['net_saving'] = sum(report['reference'][key] - report[label][key] -
                (clear.get(key, 0) if 'clear' in parts else 0) for key in ('CODE', 'BSS', 'RODATA', 'DATA'))
    report['clear_asm'] = clear
    # Standalone probes retain the installed pixel/span objects in BOTH
    # variants. Only line/rectangle/clear differ. The C oracle remains real.
    for name, source_path in (('pixel', 'src/services/display/vic_pixel.s'),
                              ('span', 'src/services/display/vic_span.s'),
                              ('stack', 'bench/graphics-pixel/stack.s'),
                              ('launcher', 'bench/graphics-raster/launcher.s')):
        subprocess.run(['ca65', '--cpu', '6502', '-o', str(work / (name + '.o')),
                        str(ROOT / source_path)], check=True)
    for number, label in enumerate(LABELS):
        text = (work / (label + '.c')).read_text()
        unit = text.split('static void increment_counter(', 1)[0]
        for name in ('unsigned_magnitude', 'udeks_vic_bitmap_line', 'udeks_vic_bitmap_rectangle'):
            unit += function(text, name)
        if label == 'reference': unit += function(text, 'udeks_vic_bitmap_clear')
        unit += (ROOT / 'bench/graphics-span/fill.c').read_text()
        path = work / (label + '-unit.c'); path.write_text(unit)
        subprocess.run(['cl65', *common, '-Oirs', '-c', '-o', str(path.with_suffix('.o')), str(path)], check=True)
        for case in range(6):
            stem = work / f'{label}-{case}'
            subprocess.run(['cl65', *common, '-D', f'VARIANT={number}', '-D', f'CASE={case}', '-c',
                '-o', str(stem.with_suffix('.o')), str(ROOT / 'bench/graphics-shared/probe.c')], check=True)
            subprocess.run(['cl65', '-t', 'none', '--cpu', '6502', '-C', str(ROOT / 'cfg/8502-raster-bench.cfg'),
                '-m', str(stem.with_suffix('.map')), '-o', str(stem.with_suffix('.bin')),
                str(work / 'launcher.o'), str(work / 'stack.o'), str(stem.with_suffix('.o')),
                str(path.with_suffix('.o')), str(work / 'pixel.o'), str(work / 'span.o'),
                *([str(work / 'clear-mechanism.o')] if number else [])], check=True)
            stem.with_suffix('.prg').write_bytes(b'\x00\x20' + stem.with_suffix('.bin').read_bytes())
    # Full experimental links: every split provider is isolated too.
    command = link_command(subprocess.check_output(['make', '-Bn', 'build/8502/udeks-8502.bin'], cwd=ROOT, text=True))
    if 'build/8502/vic_clear.o' in command:
        command.remove('build/8502/vic_clear.o')
        transport = (ROOT / 'src/8502/vic_graphics.s').read_text()
        transport, count = re.subn(r'raster_shared_placement_reserve:\n\s*\.res 294, \$ea',
                                  'raster_shared_placement_reserve:', transport)
        if count != 1: raise ValueError('shared padding changed; review reference link')
        path = work / 'reference-transport.s'; path.write_text(transport)
        subprocess.run(['ca65','--cpu','6502','-I',str(ROOT / 'src/8502'),'-o',str(path.with_suffix('.o')),str(path)],check=True)
        command[command.index('build/8502/vic_graphics_transport.o')] = str(path.with_suffix('.o'))
    maps = {}; helpers = {}
    for label in LABELS:
        directory = work / ('link-' + label); directory.mkdir(exist_ok=True)
        config = re.sub(r'file = "(build/[^"\n]+)"',
            lambda m: 'file = "' + str(directory / Path(m[1]).name) + '"',
            (ROOT / 'cfg/8502-bootstrap.cfg').read_text())
        cfg = directory / 'kernel.cfg'; cfg.write_text(config)
        local = command[:]
        local[local.index('-C')+1] = str(cfg)
        local[local.index('-m')+1] = str(directory / 'kernel.map')
        local[local.index('-o')+1] = str(directory / 'kernel.bin')
        local[local.index('build/8502/vic_graphics.o')] = str(work / (label + '.o'))
        if label == 'combined': local.append(str(work / 'clear-mechanism.o'))
        subprocess.run(local, cwd=ROOT, check=True)
        text = (directory / 'kernel.map').read_text()
        maps[label] = segments(text)
        helpers[label] = sorted(name for name in parse_map(text)[0] if 'none.lib(' in name)
    if maps['reference'] != segments((ROOT / 'bench/artifacts/2026-09-28-graphics-primitives-integration/build/8502/udeks-8502.map').read_text()):
        raise ValueError('reference link differs from preserved checkpoint')
    report['experimental_link'] = maps; report['helpers'] = helpers
    report['linked_net_saving'] = maps['reference']['BSS']['end'] - maps['combined']['BSS']['end']
    report['qualification'] = 'isolated candidate; production remains unchanged'
    report['flags'] = {'service': '-Oirs', 'driver': 'unoptimized'}
    report['cc65'] = subprocess.check_output(['cc65', '--version'], text=True, stderr=subprocess.STDOUT).strip()
    report['program_sha256'] = {f'{label}-{case}.prg': digest(work / f'{label}-{case}.prg')
                                for label in LABELS for case in range(6)}
    paths = list((ROOT / 'bench/graphics-shared').iterdir()) + list((ROOT / 'include/udeks').glob('*.h'))
    paths += [ROOT / p for p in ('src/services/display/vic_graphics.c', 'src/services/display/vic_pixel.s',
        'src/services/display/vic_span.s', 'bench/graphics-span/fill.c', 'bench/graphics-pixel/stack.s',
        'bench/graphics-raster/launcher.s', 'cfg/8502-raster-bench.cfg', 'cfg/8502-bootstrap.cfg',
        'tools/graphics_raster_bench_build.py', 'tools/graphics_span_bench.py',
        'tools/graphics_raster_link_audit.py', 'tools/graphics_raster_bench_run.py',
        'tools/1986_input_smoke_build.py', 'tools/1986_raster_bench.c', 'tools/vice_capture.py',
        'tools/placement_audit.py', 'Makefile', 'build/8502/udeks-8502.map',
        'src/8502/vic_graphics.s',
        'bench/artifacts/2026-09-28-graphics-primitives-integration/build/8502/udeks-8502.map')] + [Path(__file__), reference_source]
    report['source_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths) if path.is_file()}
    (work / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


def reference(case):
    bitmap = bytearray((i*13+7)&255 for i in range(8000)); dirty = bytearray(32)
    clip = (49,25,271,167) if case == 3 else (0,0,320,200)
    def pixel(x,y,c):
        if not (clip[0] <= x < clip[2] and clip[1] <= y < clip[3]): return
        offset = (y//8)*320 + (x//8)*8 + y%8; mask = 128 >> (x%8)
        bitmap[offset] = (bitmap[offset] | mask) if c == 0 else (bitmap[offset] & ~mask)
        dirty[offset//256] = 1
    def line(x,y,xx,yy,c):
        dx,dy = abs(xx-x),-abs(yy-y); sx,sy = (1 if x<xx else -1),(1 if y<yy else -1)
        error = dx+dy
        while True:
            pixel(x,y,c)
            if (x,y) == (xx,yy): break
            twice = error*2
            if twice>=dy: error+=dy; x+=sx
            if twice<=dx: error+=dx; y+=sy
    def rect(x,y,w,h,c):
        if w<=0 or h<=0: return
        for xx in range(x,x+w): pixel(xx,y,c); pixel(xx,y+h-1,c)
        for yy in range(y,y+h): pixel(x,yy,c); pixel(x+w-1,yy,c)
    if case == 0:
        for n in range(96):
            x,y=(n%24)*11+10,(n%16)*9+10
            line(x,y,x+17,y+11,n&1)
    elif case == 1:
        for n in range(24): line(-20,n*7,340,190-n*6,n&1)
    elif case == 2:
        xs=(-20,0,1,7,8,159,319,340); ys=(-15,0,1,7,8,99,199,215)
        for a,x in enumerate(xs):
            for b,y in enumerate(ys):
                c=(a+b)&1
                line(x,y,319-x,199-y,c); line(x,y,x,y,7)
                line(159,99,x,y,c); line(x,y,159,99,c)
        for x,y in zip(xs,ys): line(160,100,x,100,0); line(160,100,160,y,255)
    elif case == 3:
        for n in range(64):
            rect(40+(n&7),20+(n>>3),19+(n>>3),11+(n&7),n&1)
            rect(260+(n&7),155+(n>>3),1,1+(n&7),7)
        for args in ((-10,-8,350,230,0),(49,25,222,142,255),(51,27,1,1,0),
                     (52,28,1,30,0),(53,29,30,1,0),(50,26,0,20,0),(50,26,20,-1,0),
                     (320,200,10,10,0),(-20,-20,10,10,0)): rect(*args)
    elif case in (4,5): bitmap[:] = bytes([255 if case == 4 else 0])*8000; dirty[:] = bytes([1])*32
    else: raise ValueError('unknown shared case')
    return bytes(bitmap+dirty)


def decode(data, variant_number, case):
    if len(data) != 8096 or data[:8] != b'SHRD\x01\x02'+bytes((variant_number,case)):
        raise ValueError('invalid shared header/completion')
    if data[12:15] != b'\x5a\xa5\xc3' or any(data[15:64]):
        raise ValueError('shared guard/stack/reserved failure')
    ticks = int.from_bytes(data[8:12], 'little')
    if not ticks or data[64:] != reference(case):
        raise ValueError('shared timer/pixel/dirty failure')
    return ticks


def run(args):
    report = json.loads((args.work / 'build-report.json').read_text())
    def verify():
        for name, sha in report['source_sha256'].items():
            if digest(ROOT / name) != sha: raise ValueError('source drift; rebuild')
        for name, sha in report['program_sha256'].items():
            if digest(args.work / name) != sha: raise ValueError('program drift; rebuild')
    verify(); args.output.mkdir(parents=True, exist_ok=True)
    if args.engine == '1986':
        sources = importlib.import_module('1986_input_smoke_build').emulator_sources(args.emulator)
        before = emulator_provenance(args.emulator, sources)
        flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'], text=True))
        runner = args.work / '1986-shared-bench'
        subprocess.run(['cc','-std=gnu11','-O2','-I'+str(args.emulator / 'src'),
            str(ROOT / 'tools/1986_raster_bench.c'), *map(str,sources), *flags, '-lm','-o',str(runner)], check=True)
    for number,label in enumerate(LABELS):
        for case in range(6):
            program = args.work / f'{label}-{case}.prg'; raw = args.output / f'{args.engine}-{label}-{case}.bin'
            command = ([str(runner),str(program),str(raw),'SHRD'] if args.engine == '1986' else
                ['python3',str(ROOT / 'tools/vice_capture.py'),str(program),str(raw),'--entry','0x2000',
                 '--raw-load','--result-address','0x7fc0','--result-size','8096','--state-offset','5','--timeout','90'])
            subprocess.run(command, check=True)
            print(f'{args.engine} {label} {case}: {decode(raw.read_bytes(),number,case)} ticks', flush=True)
    verify()
    if args.engine == '1986':
        if before != emulator_provenance(args.emulator,sources): raise ValueError('emulator drift')
        (args.output / '1986-provenance.json').write_text(json.dumps(before,indent=2)+'\n')
    else:
        (args.output / 'VICE-flatpak.txt').write_text(subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True))
    (args.output / f'{args.engine}-run.json').write_text(json.dumps({'program_sha256':report['program_sha256'],
        'raw_sha256':{f'{args.engine}-{label}-{case}.bin':digest(args.output / f'{args.engine}-{label}-{case}.bin')
                      for label in LABELS for case in range(6)}},indent=2)+'\n')


def compare(output):
    return {str(case):{engine:{label:decode((output / f'{engine}-{label}-{case}.bin').read_bytes(),number,case)
        for number,label in enumerate(LABELS)} for engine in ('1986','vice')} for case in range(6)}


def preserve(args):
    artifact = ROOT / 'bench/artifacts' / NAME; result = ROOT / 'bench/results' / NAME
    if artifact.exists() or result.exists(): raise ValueError('refusing to replace evidence')
    report = json.loads((args.work / 'build-report.json').read_text()); timings = compare(args.output)
    for name,sha in report['source_sha256'].items():
        if digest(ROOT / name) != sha: raise ValueError('source drift')
    for name,sha in report['program_sha256'].items():
        if digest(args.work / name) != sha: raise ValueError('program drift')
    expected = {f'{label}-{case}.prg' for label in LABELS for case in range(6)}
    if set(report['program_sha256']) != expected: raise ValueError('incomplete programs')
    for engine in ('1986','vice'):
        run_manifest = json.loads((args.output / f'{engine}-run.json').read_text())
        if run_manifest['program_sha256'] != report['program_sha256']: raise ValueError('run build mismatch')
        if set(run_manifest['raw_sha256']) != {f'{engine}-{label}-{case}.bin' for label in LABELS for case in range(6)}:
            raise ValueError('incomplete records')
        for name,sha in run_manifest['raw_sha256'].items():
            if digest(args.output / name) != sha: raise ValueError('raw drift')
    artifact.mkdir(parents=True); result.mkdir(parents=True)
    for path in args.work.rglob('*'):
        if path.is_file() and path.suffix in ('.prg','.map','.c','.s','.json','.cfg'):
            target = artifact / 'build' / path.relative_to(args.work); target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
    for name in report['source_sha256']:
        target = artifact / 'sources' / name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT / name,target)
    for path in args.output.iterdir():
        if path.is_file(): shutil.copyfile(path,result / path.name)
    (result / 'report.json').write_text(json.dumps(timings,indent=2)+'\n')
    for directory in (artifact,result):
        (directory / 'SHA256SUMS').write_text(''.join(digest(path)+'  '+str(path.relative_to(directory))+'\n'
            for path in sorted(directory.rglob('*')) if path.is_file() and path.name != 'SHA256SUMS'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build','run','decode','preserve'))
    parser.add_argument('--work', type=Path, default=ROOT / 'build/graphics-shared')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/graphics-shared-results')
    parser.add_argument('--engine', choices=('1986','vice'))
    parser.add_argument('--emulator', type=Path, default=ROOT.parent / '1986')
    args = parser.parse_args()
    if args.action == 'build': build(args.work)
    elif args.action == 'run':
        if args.engine is None: parser.error('--engine required')
        run(args)
    elif args.action == 'decode': print(json.dumps(compare(args.output),indent=2))
    else: preserve(args)

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure and qualify a PRIVATE bank-1 row overlay, never patch boot disks."""
import argparse
import hashlib
import importlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/bench/window-cache-overlay'
NAME = '2026-09-28-window-cache-overlay'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'bench/window-cache-overlay'
    for name in ('core', 'gateway', 'driver'):
        if name == 'driver': continue
        subprocess.run(['ca65', '-I', str(source), '-o', str(WORK / (name+'.o')),
                        str(source / (name+'.s'))], check=True)
    subprocess.run(['ld65', '-C', str(source / 'overlay.cfg'), '-m', str(WORK / 'overlay.map'),
                    '-o', str(WORK / 'core.bin'), str(WORK / 'core.o'), str(WORK / 'gateway.o')], check=True)
    for name, path in (('driver', source / 'driver.s'), ('binding', source / 'binding.s'),
                       ('launcher', ROOT / 'bench/graphics-raster/launcher.s')):
        subprocess.run(['ca65', '-I', str(source), '-o', str(WORK / (name+'.o')), str(path)], check=True)
    from graphics_span_bench import object_sizes
    binding=object_sizes(WORK / 'binding.o')
    for case in (0,1):
        stem = WORK / f'probe-{case}'
        subprocess.run(['cc65', '-t', 'none', '--standard', 'c99', '-D', f'CASE={case}',
                        '-o', str(stem.with_suffix('.s')), str(source / 'probe.c')], check=True)
        subprocess.run(['ca65', '-o', str(stem.with_suffix('.o')), str(stem.with_suffix('.s'))], check=True)
        subprocess.run(['cl65', '-t', 'none', '-C', str(ROOT / 'cfg/8502-raster-bench.cfg'),
                        '-m', str(stem.with_suffix('.map')), '-o', str(stem.with_suffix('.bin')),
                        str(WORK / 'launcher.o'), str(stem.with_suffix('.o')),
                        str(WORK / 'driver.o'), str(WORK / 'binding.o')], check=True)
        stem.with_suffix('.prg').write_bytes(b'\x00\x20'+stem.with_suffix('.bin').read_bytes())
    # Real negative control: remove ONLY the lease's SEI, not an oracle or
    # record check. The common IRQ handler records worker-flat arrivals safely.
    normal=(WORK / 'probe-0.prg').read_bytes()
    gateway=(WORK / 'gateway.bin').read_bytes()
    # Driver has an initial diagnostic copy; the measured binding re-installs
    # its own copy at every row, so only that second copy is the live control.
    if normal.count(gateway)!=2 or gateway[10]!=0x78:raise ValueError('ambiguous SEI patch')
    offset=normal.index(gateway,normal.index(gateway)+len(gateway))+10
    negative=bytearray(normal);negative[offset]=0xea
    (WORK / 'probe-irq-leak.prg').write_bytes(negative)
    paths = list(source.iterdir()) + [Path(__file__), ROOT / 'cfg/8502-raster-bench.cfg',
        ROOT / 'bench/graphics-raster/launcher.s', ROOT / 'tools/1986_raster_bench.c',
        ROOT / 'tools/1986_input_smoke_build.py', ROOT / 'tools/graphics_raster_bench_run.py',
        ROOT / 'tools/vice_capture.py']
    report = {
        'qualification': 'standalone active-IRQ row proof; no production delivery/state/GUI qualification',
        'core_bytes': (WORK / 'core.bin').stat().st_size,
        'gateway_bytes': (WORK / 'gateway.bin').stat().st_size,
        'binding_object':binding,
        'core_reservation': [0x4200,0x43ff], 'cache_reservation': [0x4400,0x5bff],
        'row_stage': [0xf7b0,0xf7d7], 'parameters': [0xf780,0xf789],
        'diagnostic_guard_parameter': [0xf78a,0xf78b],
        'negative_control': {'program':'probe-irq-leak.prg','offset':offset,'before':0x78,'after':0xea},
        'cc65': subprocess.check_output(['cc65','--version'], stderr=subprocess.STDOUT,text=True).strip(),
        'source_sha256': {str(p.relative_to(ROOT)):digest(p) for p in sorted(paths) if p.is_file()},
        'program_sha256': {f'probe-{case}.prg':digest(WORK / f'probe-{case}.prg') for case in (0,1)}}
    report['program_sha256']['probe-irq-leak.prg']=digest(WORK / 'probe-irq-leak.prg')
    if report['core_bytes'] > 512 or report['gateway_bytes'] > 246:
        raise ValueError('overlay placement exceeded')
    (WORK / 'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


def verify(report):
    for name,sha in report['source_sha256'].items():
        if digest(ROOT / name) != sha: raise ValueError('source drift: '+name)
    for name,sha in report['program_sha256'].items():
        if digest(WORK / name) != sha: raise ValueError('program drift: '+name)


def run(engine, output, emulator):
    from graphics_raster_bench_run import emulator_provenance
    report = json.loads((WORK / 'build-report.json').read_text()); verify(report)
    output.mkdir(parents=True,exist_ok=True)
    if engine == '1986':
        sources = importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
        before = emulator_provenance(emulator,sources)
        flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
        runner = WORK / '1986-overlay-bench'
        subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator / 'src'),
            str(ROOT / 'tools/1986_raster_bench.c'),*map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    else:
        identity = subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True)
        (output / 'vice-provenance.txt').write_text(identity)
    for case in (0,1,'irq-leak'):
        program = WORK / f'probe-{case}.prg'; raw = output / f'{engine}-{case}.bin'
        command = ([str(runner),str(program),str(raw),'OROW'] if engine == '1986' else
            ['python3',str(ROOT / 'tools/vice_capture.py'),str(program),str(raw),
             '--entry','0x2000','--raw-load','--result-address','0x7fc0',
             '--result-size','8096','--state-offset','5','--timeout','90'])
        subprocess.run(command,check=True)
        if case=='irq-leak':
            data=raw.read_bytes()
            if len(data)!=8096 or data[:8]!=b'OROW\x01\x02\x00\x00' or data[14]!=1:
                raise ValueError('negative control did not detect worker-flat IRQ')
            try:decode(data,0)
            except ValueError:print('negative control: unsafe worker-flat IRQ rejected',flush=True)
            else:raise ValueError('negative control passed decoder')
        else:print(json.dumps(decode(raw.read_bytes(),case)),flush=True)
    verify(report)
    if engine == '1986':
        if emulator_provenance(emulator,sources) != before: raise ValueError('emulator drift')
        (output / '1986-provenance.json').write_text(json.dumps(before,indent=2)+'\n')
    (output / f'{engine}-run.json').write_text(json.dumps({
        'program_sha256':report['program_sha256'],
        'raw_sha256':{f'{engine}-{case}.bin':digest(output / f'{engine}-{case}.bin') for case in (0,1,'irq-leak')}},indent=2)+'\n')


def reference(case):
    # Independent per-pixel oracle. Matrix source rows are untouched by its
    # destination rows; the large case replaces the entire background first.
    source = bytes((i*13+7)&255 for i in range(8000))
    bitmap = bytearray(source if case == 0 else bytes((i*31+19)&255 for i in range(8000)))
    dirty = bytearray(32)
    moves = ([(a,128,b,a*8+b,17,1) for a in range(8) for b in range(8)] +
        [(0,129,0,64,320,1),(319,199,319,199,1,1)] if case == 0 else [(7,7,100,40,220,160)])
    for x,y,xx,yy,w,h in moves:
        for row in range(h):
            for column in range(w):
                sx,sy,dx,dy=x+column,y+row,xx+column,yy+row
                so=sy//8*320+sx//8*8+sy%8; off=dy//8*320+dx//8*8+dy%8
                mask=128>>(dx%8)
                if source[so] & (128>>(sx%8)):bitmap[off]|=mask
                else:bitmap[off]&=255^mask
                dirty[off//256]=1
    return bytes(bitmap+dirty)


def decode(data,case):
    if len(data)!=8096 or data[:8]!=b'OROW\x01\x02'+bytes((case,0)):
        raise ValueError('invalid row proof header or failure')
    rows=132 if case==0 else 320; images=66 if case==0 else 1
    if int.from_bytes(data[8:10],'little')!=rows or data[10]!=images or data[11]!=0:
        raise ValueError('incomplete row/image count')
    irq=int.from_bytes(data[12:14],'little')
    if (not irq or any(data[14:16]) or data[16:18]!=b'\x5a\xa5' or
            data[18]!=0 or data[19]!=0xa5 or any(data[20:64])):
        raise ValueError('IRQ mapping/flags/stack/guard failure')
    if data[64:] != reference(case): raise ValueError('bitmap/dirty mismatch')
    return {'case':case,'row_calls':rows,'images':images,'interrupts':irq,
            'pixels_dirty_sha256':hashlib.sha256(data[64:]).hexdigest()}


def preserve(output):
    report=json.loads((WORK / 'build-report.json').read_text());verify(report)
    result={'qualification':report['qualification'],'cases':[]}
    for engine in ('1986','vice'):
        run_report=json.loads((output / f'{engine}-run.json').read_text())
        if run_report['program_sha256']!=report['program_sha256']:raise ValueError('wrong build')
        if set(run_report['raw_sha256'])!={f'{engine}-{case}.bin' for case in (0,1,'irq-leak')}:
            raise ValueError('incomplete raw record set')
        for name,sha in run_report['raw_sha256'].items():
            if digest(output / name)!=sha:raise ValueError('record drift')
        leak=(output / f'{engine}-irq-leak.bin').read_bytes()
        if len(leak)!=8096 or leak[:8]!=b'OROW\x01\x02\x00\x00' or leak[14]!=1:
            raise ValueError('missing negative-control IRQ evidence')
    for case in (0,1):
        result['cases'].append({engine:decode((output / f'{engine}-{case}.bin').read_bytes(),case)
                               for engine in ('1986','vice')})
    artifacts=ROOT / 'bench/artifacts' / NAME;results=ROOT / 'bench/results' / NAME
    if artifacts.exists() or results.exists():raise ValueError('refusing to overwrite evidence')
    artifacts.mkdir(parents=True);results.mkdir(parents=True)
    for name in report['source_sha256']:
        target=artifacts / name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT / name,target)
    build_dir=artifacts / 'build';build_dir.mkdir()
    for path in WORK.iterdir():
        if path.suffix in ('.prg','.bin','.map','.json'):shutil.copy2(path,build_dir / path.name)
    for path in output.iterdir():shutil.copy2(path,results / path.name)
    (results / 'report.json').write_text(json.dumps(result,indent=2)+'\n')
    for directory in (artifacts,results):
        paths=sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))
    print(json.dumps(result,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('build','run','decode','preserve'))
    parser.add_argument('--engine',choices=('1986','vice'))
    parser.add_argument('--emulator',type=Path,default=ROOT.parent / '1986')
    parser.add_argument('--output',type=Path,default=ROOT / 'build/bench/window-cache-overlay-results')
    args=parser.parse_args()
    if args.action=='build':build()
    elif args.action=='run':
        if args.engine is None:parser.error('run requires --engine')
        run(args.engine,args.output,args.emulator)
    elif args.action=='preserve':preserve(args.output)
    else:
        for engine in ('1986','vice'):
            for case in (0,1):print(engine,decode((args.output / f'{engine}-{case}.bin').read_bytes(),case))


if __name__=='__main__':main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone qualification of the public cc65 pixel ABI; no OS installation."""
import argparse
import importlib
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from graphics_span_bench import ROOT, digest, object_sizes, replace_fill
from graphics_raster_bench_build import function
from graphics_raster_link_audit import link_command, segments
from graphics_raster_bench_run import emulator_provenance
from placement_audit import parse_map
from gen_capability_imports import map_exports

NAME='2026-09-28-graphics-pixel'
LABELS=('c-reference','asm-pixel')


def replace_pixel(source):
    old=function(source,'udeks_vic_bitmap_pixel').rstrip()
    if source.count(old)!=1: raise ValueError('ambiguous pixel entry')
    return source.replace(old,'/* Pixel entry supplied by the isolated ASM object. */')


def build(work):
    work.mkdir(parents=True,exist_ok=True)
    source=(ROOT/'src/services/display/vic_graphics.c').read_text()
    common=['-t','none','--cpu','6502','--standard','c99','-I',str(ROOT/'include')]
    report={'qualification':'standalone pixel ABI; not an installed display service',
            'cc65':subprocess.check_output(['cc65','--version'],text=True,stderr=subprocess.STDOUT).strip(),
            'flags':{'service':'-Oirs','driver':'unoptimized'}}
    for name,path in (('pixel','bench/graphics-pixel/pixel.s'),('stack','bench/graphics-pixel/stack.s'),
                      ('launcher','bench/graphics-raster/launcher.s')):
        subprocess.run(['ca65','--cpu','6502','-o',str(work/f'{name}.o'),str(ROOT/path)],check=True)
    for variant,label in enumerate(LABELS):
        full=work/f'{label}-full.c';full.write_text(source if variant==0 else replace_pixel(source))
        subprocess.run(['cl65',*common,'-Oirs','-c','-o',str(full.with_suffix('.o')),str(full)],check=True)
        report[label]=object_sizes(full.with_suffix('.o'))
        unit=work/f'{label}.c'
        unit.write_text(source.split('static void increment_counter(',1)[0]+(
            function(source,'udeks_vic_bitmap_pixel') if variant==0 else ''))
        subprocess.run(['cl65',*common,'-Oirs','-c','-o',str(unit.with_suffix('.o')),str(unit)],check=True)
        for case in range(4):
            stem=work/f'{label}-{case}'
            subprocess.run(['cl65',*common,'-D',f'VARIANT={variant}','-D',f'CASE={case}','-c',
                '-o',str(stem.with_suffix('.o')),str(ROOT/'bench/graphics-pixel/probe.c')],check=True)
            subprocess.run(['cl65','-t','none','--cpu','6502','-C',str(ROOT/'cfg/8502-raster-bench.cfg'),
                '-m',str(stem.with_suffix('.map')),'-o',str(stem.with_suffix('.bin')),str(work/'launcher.o'),
                str(work/'stack.o'),str(stem.with_suffix('.o')),str(unit.with_suffix('.o')),
                *([str(work/'pixel.o')] if variant else [])],check=True)
            stem.with_suffix('.prg').write_bytes(b'\x00\x20'+stem.with_suffix('.bin').read_bytes())
    report['pixel']=object_sizes(work/'pixel.o')
    report['object_net_saving']=sum(report['c-reference'][n]-report['asm-pixel'][n]-report['pixel'][n]
                                     for n in ('CODE','RODATA','DATA','BSS'))
    # Also measure the combined fill/pixel candidate, retargeting ALL side outputs.
    combined=work/'combined-full.c';combined.write_text(replace_pixel(replace_fill(source)))
    subprocess.run(['cl65',*common,'-Oirs','-c','-o',str(combined.with_suffix('.o')),str(combined)],check=True)
    subprocess.run(['ca65','--cpu','6502','-o',str(work/'span.o'),str(ROOT/'bench/graphics-span/span.s')],check=True)
    command=link_command(subprocess.check_output(['make','-Bn','build/8502/udeks-8502.bin'],cwd=ROOT,text=True))
    maps={};helpers={}
    for label in (*LABELS,'combined'):
        directory=work/f'link-{label}';directory.mkdir(exist_ok=True)
        cfg=re.sub(r'file = "(build/[^"\n]+)"',lambda m:'file = "'+str(directory/Path(m[1]).name)+'"',
                   (ROOT/'cfg/8502-bootstrap.cfg').read_text())
        config=directory/'kernel.cfg';config.write_text(cfg)
        local=command[:]
        local[local.index('-C')+1]=str(config);local[local.index('-m')+1]=str(directory/'kernel.map')
        local[local.index('-o')+1]=str(directory/'kernel.bin')
        local[local.index('build/8502/vic_graphics.o')]=str(combined.with_suffix('.o') if label=='combined'
                                                        else work/f'{label}-full.o')
        if label!='c-reference':local.append(str(work/'pixel.o'))
        if label=='combined':local.append(str(work/'span.o'))
        subprocess.run(local,cwd=ROOT,check=True)
        text=(directory/'kernel.map').read_text();maps[label]=segments(text)
        helpers[label]=sorted(n for n in parse_map(text)[0] if 'none.lib(' in n)
    if maps['c-reference']!=segments((ROOT/'build/8502/udeks-8502.map').read_text()):
        raise ValueError('baseline differs from production map')
    report['experimental_link']=maps;report['helpers']=helpers
    report['linked_net_saving']=maps['c-reference']['BSS']['end']-maps['asm-pixel']['BSS']['end']
    report['combined_net_saving']=maps['c-reference']['BSS']['end']-maps['combined']['BSS']['end']
    report['program_sha256']={f'{label}-{case}.prg':digest(work/f'{label}-{case}.prg')
                             for label in LABELS for case in range(4)}
    paths=[ROOT/p for p in ('src/services/display/vic_graphics.c','bench/graphics-raster/launcher.s',
        'bench/graphics-span/fill.c','bench/graphics-span/span.s','cfg/8502-raster-bench.cfg','cfg/8502-bootstrap.cfg',
        'tools/graphics_span_bench.py','tools/graphics_raster_bench_build.py','tools/graphics_raster_link_audit.py',
        'tools/graphics_raster_bench_run.py','tools/1986_input_smoke_build.py','tools/1986_raster_bench.c',
        'tools/vice_capture.py','Makefile','build/8502/udeks-8502.map')]+list((ROOT/'bench/graphics-pixel').iterdir())
    paths+=list((ROOT/'include/udeks').glob('*.h'))+[Path(__file__)]
    report['source_sha256']={str(p.relative_to(ROOT)):digest(p) for p in sorted(paths) if p.is_file()}
    (work/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({n:report[n] for n in ('pixel','object_net_saving','linked_net_saving','combined_net_saving')},indent=2))


def reference(case):
    bitmap=bytearray((i*13+7)&255 for i in range(8000));dirty=bytearray(32)
    def pixel(x,y,c,clip=(0,0,320,200)):
        if not (clip[0]<=x<clip[2] and clip[1]<=y<clip[3]):return
        off=(y//8)*320+(x//8)*8+y%8;mask=128>>(x%8)
        bitmap[off]=(bitmap[off]|mask) if c==0 else (bitmap[off]&~mask)
        dirty[off//256]=1
    if case==0:
        for c in range(2):
            for a in range(8):
                for b in range(8):pixel(8+a,c*64+a*8+b,c)
        for y in range(200):pixel(319,y,7)
        pixel(0,0,0);pixel(0,199,255)
    elif case==1:
        clip=(49,25,271,167)
        for y in range(24,168):
            for x,c in ((48,0),(49,0),(270,7),(271,7)):pixel(x,y,c,clip)
        for x in range(48,272):
            for y,c in ((24,0),(25,0),(166,255),(167,255)):pixel(x,y,c,clip)
        for x,y in ((-32768,30),(32767,30),(60,-32768),(60,32767),(-1,30),(60,-1)):pixel(x,y,0,clip)
    elif case==2:pixel(240,0,0);pixel(261,0,255)
    elif case==3:
        for i in range(1024):pixel((i*37)%320,(i*17)%200,i&1)
    else:raise ValueError('unknown pixel case')
    return bytes(bitmap+dirty)


def decode(data,variant,case):
    if len(data)!=8096 or data[:8]!=b'PIXL\x01\x02'+bytes((variant,case)):
        raise ValueError('pixel header/completion failure')
    if data[12:15]!=b'\x5a\xa5\xc3' or any(data[15:64]):raise ValueError('pixel guard/stack/reserved failure')
    count=int.from_bytes(data[8:12],'little')
    if not count or data[64:]!=reference(case):raise ValueError('pixel timer/bitmap/dirty failure')
    return count


def run(args):
    report=json.loads((args.work/'build-report.json').read_text())
    def verify():
        for name,sha in report['source_sha256'].items():
            if digest(ROOT/name)!=sha:raise ValueError('source drift; rebuild')
        for name,sha in report['program_sha256'].items():
            if digest(args.work/name)!=sha:raise ValueError('program drift; rebuild')
    verify();args.output.mkdir(parents=True,exist_ok=True)
    if args.engine=='1986':
        sources=importlib.import_module('1986_input_smoke_build').emulator_sources(args.emulator)
        before=emulator_provenance(args.emulator,sources)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
        runner=args.work/'1986-pixel-bench'
        subprocess.run(['cc','-std=gnu11','-O2','-I'+str(args.emulator/'src'),str(ROOT/'tools/1986_raster_bench.c'),
                        *map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    for variant,label in enumerate(LABELS):
        for case in range(4):
            program=args.work/f'{label}-{case}.prg';raw=args.output/f'{args.engine}-{label}-{case}.bin'
            command=([str(runner),str(program),str(raw),'PIXL'] if args.engine=='1986' else
                ['python3',str(ROOT/'tools/vice_capture.py'),str(program),str(raw),'--entry','0x2000',
                 '--raw-load','--result-address','0x7fc0','--result-size','8096','--state-offset','5','--timeout','90'])
            subprocess.run(command,check=True)
            print(f'{args.engine} {label} {case}: {decode(raw.read_bytes(),variant,case)} ticks',flush=True)
    verify()
    if args.engine=='1986':
        if before!=emulator_provenance(args.emulator,sources):raise ValueError('emulator drift')
        (args.output/'1986-provenance.json').write_text(json.dumps(before,indent=2)+'\n')
    else:(args.output/'VICE-flatpak.txt').write_text(subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True))
    (args.output/f'{args.engine}-run.json').write_text(json.dumps({'program_sha256':report['program_sha256'],
        'raw_sha256':{f'{args.engine}-{label}-{case}.bin':digest(args.output/f'{args.engine}-{label}-{case}.bin')
                      for label in LABELS for case in range(4)}},indent=2)+'\n')


def compare(output):
    return {str(case):{engine:{label:decode((output/f'{engine}-{label}-{case}.bin').read_bytes(),variant,case)
            for variant,label in enumerate(LABELS)} for engine in ('1986','vice')} for case in range(4)}


def preserve(args):
    artifact=ROOT/'bench/artifacts'/NAME;result=ROOT/'bench/results'/NAME
    if artifact.exists() or result.exists():raise ValueError('refusing to overwrite evidence')
    report=json.loads((args.work/'build-report.json').read_text());timings=compare(args.output)
    expected={f'{label}-{case}.prg' for label in LABELS for case in range(4)}
    if set(report['program_sha256'])!=expected:raise ValueError('incomplete program manifest')
    for name,sha in report['source_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('source drift')
    for name,sha in report['program_sha256'].items():
        if digest(args.work/name)!=sha:raise ValueError('program drift')
    for engine in ('1986','vice'):
        run=json.loads((args.output/f'{engine}-run.json').read_text())
        if run['program_sha256']!=report['program_sha256']:raise ValueError('run bound to another build')
        if set(run['raw_sha256'])!={f'{engine}-{label}-{case}.bin' for label in LABELS for case in range(4)}:
            raise ValueError('incomplete raw manifest')
        for name,sha in run['raw_sha256'].items():
            if digest(args.output/name)!=sha:raise ValueError('raw drift')
    artifact.mkdir(parents=True);result.mkdir(parents=True)
    for path in args.work.rglob('*'):
        if path.is_file() and path.suffix in ('.prg','.map','.c','.s','.json','.cfg'):
            dest=artifact/'build'/path.relative_to(args.work);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,dest)
    for name in report['source_sha256']:
        dest=artifact/'sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    for path in args.output.iterdir():
        if path.is_file():shutil.copyfile(path,result/path.name)
    (result/'report.json').write_text(json.dumps(timings,indent=2)+'\n')
    for directory in (artifact,result):
        (directory/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(directory))+'\n'
            for p in sorted(directory.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('build','run','decode','preserve'))
    parser.add_argument('--work',type=Path,default=ROOT/'build/graphics-pixel')
    parser.add_argument('--output',type=Path,default=ROOT/'build/graphics-pixel-results')
    parser.add_argument('--engine',choices=('1986','vice'))
    parser.add_argument('--emulator',type=Path,default=ROOT.parent/'1986')
    args=parser.parse_args()
    if args.action=='build':build(args.work)
    elif args.action=='run':
        if args.engine is None:parser.error('--engine required')
        run(args)
    elif args.action=='decode':print(json.dumps(compare(args.output),indent=2))
    else:preserve(args)


if __name__=='__main__':main()

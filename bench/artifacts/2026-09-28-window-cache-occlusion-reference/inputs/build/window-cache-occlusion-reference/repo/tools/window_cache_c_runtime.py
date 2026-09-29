#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone private C stack/dispatcher + row-blitter proof. No boot changes."""
import argparse
import hashlib
import importlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT / 'build/bench/window-cache-c-runtime'
NAME='2026-09-28-window-cache-c-runtime'
PROOF=ROOT / 'bench/artifacts/2026-09-28-window-cache-overlay'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    from graphics_span_bench import object_sizes
    from placement_audit import parse_map
    WORK.mkdir(parents=True,exist_ok=True)
    source=ROOT / 'bench/window-cache-c-runtime'
    qualified=PROOF / 'bench/window-cache-overlay'
    for line in (PROOF / 'SHA256SUMS').read_text().splitlines():
        sha,name=line.split('  ',1)
        if digest(PROOF / name)!=sha:raise ValueError('qualified row proof changed')
    policy=WORK / 'policy.o'
    subprocess.run(['cl65','-t','none','--cpu','6502','-Oirs','--standard','c99',
        '-I',str(ROOT / 'include'),'-c','-o',str(policy),
        str(ROOT / 'src/services/window/move_cache_state.c')],check=True)
    records={}
    for name in ('lease','geometry','row'):
        probe=WORK / f'size-{name}.c'
        probe.write_text('#include "udeks/window_cache_state.h"\nstruct udeks_cache_'+name+' record;\n')
        subprocess.run(['cl65','-t','none','-I',str(ROOT / 'include'),'-c',
            '-o',str(probe.with_suffix('.o')),str(probe)],check=True)
        records[name]=object_sizes(probe.with_suffix('.o'))['BSS']
    if records!={'lease':13,'geometry':6,'row':9}:raise ValueError('private C records moved')
    for name,path,include in (('core',qualified / 'core.s',qualified),
            ('row-gateway',qualified / 'gateway.s',qualified),
            ('module',source / 'module.s',source),('c-gateway',source / 'gateway.s',source)):
        subprocess.run(['ca65','-I',str(include),'-o',str(WORK / (name+'.o')),str(path)],check=True)
    subprocess.run(['ld65','-C',str(source / 'gateway.cfg'),
        '-o',str(WORK / 'row-gateway.bin'),str(WORK / 'row-gateway.o')],check=True)
    if (WORK / 'row-gateway.bin').read_bytes()!=(PROOF / 'build/gateway.bin').read_bytes():
        raise ValueError('row gateway drift')
    subprocess.run(['ld65','-C',str(source / 'gateway.cfg'),
        '-o',str(WORK / 'c-gateway.bin'),str(WORK / 'c-gateway.o')],check=True)
    subprocess.run(['cl65','-t','none','--cpu','6502','-C',str(source / 'module.cfg'),
        '-m',str(WORK / 'module.map'),'-o',str(WORK / 'module.bin'),
        str(WORK / 'core.o'),str(WORK / 'module.o'),str(policy)],check=True)
    module=(WORK / 'module.bin').read_bytes()
    if module[:213]!=(PROOF / 'build/core.bin').read_bytes():raise ValueError('row core drift')
    if len(module)>0xad0:raise ValueError('module reaches private state')
    (WORK / 'module-envelope.bin').write_bytes(module.ljust(0xb00,b'\x00'))
    binding=(qualified / 'binding.s').read_text().replace(
        'build/bench/window-cache-overlay/gateway.bin',
        'build/bench/window-cache-c-runtime/row-gateway.bin')
    (WORK / 'row-binding.s').write_text(binding)
    launcher=(ROOT / 'bench/graphics-raster/launcher.s').read_text()
    for old,new in (('lda #<$7800','lda #<$eff0'),('lda #>$7800','lda #>$eff0')):
        if launcher.count(old)!=1:raise ValueError('diagnostic caller stack initializer changed')
        launcher=launcher.replace(old,new)
    (WORK / 'launcher.s').write_text(launcher)
    for name,path,include in (('binding',source / 'binding.s',source),
            ('row-binding',WORK / 'row-binding.s',qualified),
            ('driver',source / 'driver.s',source),
            ('launcher',WORK / 'launcher.s',source)):
        subprocess.run(['ca65','-I',str(include),'-o',str(WORK / (name+'.o')),str(path)],check=True)
    for case in (0,1):
        stem=WORK / f'probe-{case}'
        subprocess.run(['cc65','-t','none','--standard','c99','-Oirs','-D',f'CASE={case}',
            '-o',str(stem.with_suffix('.s')),str(source / 'probe.c')],check=True)
        subprocess.run(['ca65','-o',str(stem.with_suffix('.o')),str(stem.with_suffix('.s'))],check=True)
        subprocess.run(['cl65','-t','none','-C',str(source / 'probe.cfg'),
            '-m',str(stem.with_suffix('.map')),'-o',str(stem.with_suffix('.bin')),
            *[str(WORK / (n+'.o')) for n in ('launcher',f'probe-{case}','driver','binding','row-binding')]],check=True)
        stem.with_suffix('.prg').write_bytes(b'\x00\x20'+stem.with_suffix('.bin').read_bytes())
        _,probe_segments=parse_map(stem.with_suffix('.map').read_text())
        if {n:(s,e) for n,s,e in probe_segments}['ZEROPAGE']!=(6,31):
            raise ValueError('caller runtime allocation moved')
    normal=(WORK / 'probe-0.prg').read_bytes();gate=(WORK / 'c-gateway.bin').read_bytes()
    if normal.count(gate)!=1 or gate[1]!=0x78:raise ValueError('ambiguous live C gateway')
    start=normal.index(gate)
    controls={}
    patterns={'irq-leak':(b'\x08\x78\xd8',1,0xea),
              'zp-leak':(b'\x68\x95\x06\xe8',2,0x07),
              'shell-stack':(b'\xa9\x4d\x85\x07',1,0xef)}
    for name,(pattern,delta,new) in patterns.items():
        if gate.count(pattern)!=1:raise ValueError('ambiguous negative control '+name)
        offset=start+gate.index(pattern)+delta
        image=bytearray(normal);old=image[offset];image[offset]=new
        (WORK / f'probe-{name}.prg').write_bytes(image)
        controls[name]={'offset':offset,'before':old,'after':new}
    objects,segments=parse_map((WORK / 'module.map').read_text())
    by_name={n:(s,e) for n,s,e in segments}
    if by_name['ZEROPAGE']!=(6,31) or by_name['PRIVATESTATE']!=(0x4cd0,0x4ceb):
        raise ValueError('compiler runtime/private records moved')
    paths=list(source.iterdir())+[Path(__file__),ROOT / 'src/services/window/move_cache_state.c',
        ROOT / 'include/udeks/window_cache_state.h',ROOT / 'bench/graphics-raster/launcher.s',
        ROOT / 'tools/1986_raster_bench.c',ROOT / 'tools/1986_input_smoke_build.py',
        ROOT / 'tools/graphics_raster_bench_run.py',ROOT / 'tools/graphics_span_bench.py',
        ROOT / 'tools/placement_audit.py',ROOT / 'tools/vice_capture.py']
    paths += [qualified / name for name in ('core.s','gateway.s','binding.s','layout.inc')]
    paths += [PROOF / 'build/core.bin',PROOF / 'build/gateway.bin']
    linked=('module.bin','module-envelope.bin','module.map','c-gateway.bin','row-gateway.bin',
            'probe-0.bin','probe-0.map','probe-1.bin','probe-1.map','launcher.s','row-binding.s')
    report={'qualification':'standalone private-C/row proof, not production or NMI/input qualification',
        'cc65':subprocess.check_output(['cc65','--version'],stderr=subprocess.STDOUT,text=True).strip(),
        'module_bytes':len(module),'module_state_bytes':28,
        'cc65_record_bytes':records,
        'module_segments':{n:[s,e] for n,s,e in segments},
        'policy_object':object_sizes(policy),'dispatcher_object':object_sizes(WORK / 'module.o'),
        'c_binding_object':object_sizes(WORK / 'binding.o'),
        'row_binding_object':object_sizes(WORK / 'row-binding.o'),
        'c_gateway_bytes':len(gate),'row_gateway_bytes':170,
        'candidate_private_stack':[0x4d00,0x4def],'candidate_image':[0x4e00,0x5bff],
        'caller_stack_top':0xeff0,'protected_worker_shell_stack':[0xe700,0xefff],
        'negative_controls':controls,'helpers':sorted(n for n in objects if 'none.lib(' in n),
        'linked_sha256':{name:digest(WORK / name) for name in linked},
        'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in sorted(paths) if p.is_file()},
        'program_sha256':{p.name:digest(p) for p in sorted(WORK.glob('probe-*.prg'))}}
    (WORK / 'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256','program_sha256','helpers')},indent=2))


def verify(report):
    for name,sha in report['source_sha256'].items():
        if digest(ROOT / name)!=sha:raise ValueError('source drift '+name)
    for name,sha in report['program_sha256'].items():
        if digest(WORK / name)!=sha:raise ValueError('program drift '+name)
    for name,sha in report['linked_sha256'].items():
        if digest(WORK / name)!=sha:raise ValueError('link/binding drift '+name)


def reference(case):
    source=bytes((i*13+7)&255 for i in range(8000))
    bitmap=bytearray(source if case==0 else bytes((i*31+19)&255 for i in range(8000)))
    dirty=bytearray(32)
    moves=([(a,128,b,a*8+b,17,1) for a in range(8) for b in range(8)]+
           [(0,129,0,64,320,1),(319,199,319,199,1,1)] if case==0 else [(7,7,100,40,168,104)])
    for x,y,xx,yy,w,h in moves:
        for row in range(h):
            for column in range(w):
                sx,sy,dx,dy=x+column,y+row,xx+column,yy+row
                so=(sy//8)*320+(sx//8)*8+sy%8
                dest=(dy//8)*320+(dx//8)*8+dy%8;mask=128>>(dx%8)
                if source[so] & (128>>(sx%8)):bitmap[dest]|=mask
                else:bitmap[dest]&=255^mask
                dirty[dest//256]=1
    return bytes(bitmap+dirty)


def facts(data,case):
    if case not in (0,1):raise ValueError('unknown diagnostic case')
    if len(data)!=8096 or data[:8]!=b'CRUN\x01\x02'+bytes((case,0)):
        raise ValueError('C-runtime header/semantic failure')
    rows,calls,images=(132,547,66) if case==0 else (208,439,1)
    if (int.from_bytes(data[8:10],'little')!=rows or
        int.from_bytes(data[10:12],'little')!=calls or data[14]!=images):
        raise ValueError('incomplete calls/rows/images')
    irq=int.from_bytes(data[12:14]+data[24:26],'little')
    if not irq or data[23]!=15 or any(data[26:64]):
        raise ValueError('IRQ/flag coverage/reserved record failure')
    if data[64:]!=reference(case):raise ValueError('bitmap/dirty mismatch')
    return rows,calls,images,irq


def decode(data,case):
    rows,calls,images,irq=facts(data,case)
    if any(data[15:22]) or not 0x40<=data[22]<0xf0:
        raise ValueError('IRQ/runtime/private-stack/guard qualification failed')
    return {'case':case,'rows':rows,'policy_calls':calls,'images':images,'interrupts':irq,
        'lowest_observed_changed_stack_offset':data[22],
        'bitmap_dirty_sha256':hashlib.sha256(data[64:]).hexdigest()}


def negative(data,name):
    facts(data,0)
    required={'irq-leak':(15,), 'zp-leak':(16,), 'shell-stack':(19,21)}[name]
    if any(data[i]!=(1 if i in required else 0) for i in range(15,22)):
        raise ValueError('negative control missing or unexpected failure '+name)
    if name=='shell-stack':
        if data[22]!=0xf0:raise ValueError('shell-stack control used private stack')
    elif not 0x40<=data[22]<0xf0:raise ValueError('negative private stack not exercised')
    try:decode(data,0)
    except ValueError:pass
    else:raise ValueError('negative control passed normal decoder')
    return {'detected_fields':list(required)}


def run(engine,output,emulator):
    from graphics_raster_bench_run import emulator_provenance
    report=json.loads((WORK / 'build-report.json').read_text());verify(report)
    output.mkdir(parents=True,exist_ok=True)
    if engine=='1986':
        sources=importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
        before=emulator_provenance(emulator,sources)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
        runner=WORK / '1986-c-runtime'
        subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator / 'src'),
            str(ROOT / 'tools/1986_raster_bench.c'),*map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    else:
        (output / 'vice-provenance.txt').write_text(subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True))
    decoded={}
    for case in (0,1,'irq-leak','zp-leak','shell-stack'):
        program=WORK / f'probe-{case}.prg';raw=output / f'{engine}-{case}.bin'
        command=([str(runner),str(program),str(raw),'CRUN'] if engine=='1986' else
            ['python3',str(ROOT / 'tools/vice_capture.py'),str(program),str(raw),
             '--entry','0x2000','--raw-load','--result-address','0x7fc0',
             '--result-size','8096','--state-offset','5','--timeout','90'])
        subprocess.run(command,check=True)
        decoded[str(case)]=decode(raw.read_bytes(),case) if isinstance(case,int) else negative(raw.read_bytes(),case)
        print(json.dumps(decoded[str(case)]),flush=True)
    verify(report)
    if engine=='1986':
        if emulator_provenance(emulator,sources)!=before:raise ValueError('emulator drift')
        (output / '1986-provenance.json').write_text(json.dumps(before,indent=2)+'\n')
    (output / f'{engine}-run.json').write_text(json.dumps({'program_sha256':report['program_sha256'],
        'raw_sha256':{f'{engine}-{case}.bin':digest(output / f'{engine}-{case}.bin') for case in decoded},
        'decoded':decoded},indent=2)+'\n')


def preserve(output):
    report=json.loads((WORK / 'build-report.json').read_text());verify(report)
    results_report={}
    for engine in ('1986','vice'):
        run_report=json.loads((output / f'{engine}-run.json').read_text())
        if run_report['program_sha256']!=report['program_sha256']:raise ValueError('wrong build')
        expected={f'{engine}-{case}.bin' for case in (0,1,'irq-leak','zp-leak','shell-stack')}
        if set(run_report['raw_sha256'])!=expected:raise ValueError('incomplete run')
        for name,sha in run_report['raw_sha256'].items():
            if digest(output / name)!=sha:raise ValueError('raw record drift')
        results_report[engine]={str(c):decode((output / f'{engine}-{c}.bin').read_bytes(),c) for c in (0,1)}
        for name in ('irq-leak','zp-leak','shell-stack'):
            results_report[engine][name]=negative((output / f'{engine}-{name}.bin').read_bytes(),name)
        if run_report['decoded']!=results_report[engine]:raise ValueError('decoded report drift')
    artifacts=ROOT / 'bench/artifacts' / NAME;results=ROOT / 'bench/results' / NAME
    if artifacts.exists() or results.exists():raise ValueError('refusing to overwrite evidence')
    artifacts.mkdir(parents=True);results.mkdir(parents=True)
    for name in report['source_sha256']:
        target=artifacts / name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT / name,target)
    dest=artifacts / 'build';dest.mkdir()
    for name in sorted(set(report['linked_sha256'])|set(report['program_sha256'])|{'build-report.json'}):
        shutil.copy2(WORK / name,dest / name)
    for path in output.iterdir():
        if path.suffix in ('.bin','.json','.txt'):shutil.copy2(path,results / path.name)
    (results / 'report.json').write_text(json.dumps(results_report,indent=2)+'\n')
    for directory in (artifacts,results):
        paths=sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))
    print(json.dumps(results_report,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('build','run','decode','preserve'))
    parser.add_argument('--engine',choices=('1986','vice'))
    parser.add_argument('--emulator',type=Path,default=ROOT.parent / '1986')
    parser.add_argument('--output',type=Path,default=ROOT / 'build/bench/window-cache-c-runtime-results')
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

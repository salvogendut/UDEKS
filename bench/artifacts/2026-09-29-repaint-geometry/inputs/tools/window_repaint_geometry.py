#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure private 8502 damage primitives; no normal-image mutation."""
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import shlex
import shutil
import subprocess
from graphics_raster_bench_build import function
from graphics_span_bench import object_sizes
from graphics_raster_link_audit import link_command, segments
from window_repaint_compact import isolated_config, library_inventory
import window_repaint_scenes as scenes
import window_repaint_raster as raster

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT / 'build/window-repaint-geometry'
SOURCE=ROOT / 'bench/window-repaint-geometry'
RESULT=ROOT / 'build/window-repaint-geometry-results'
NAME='2026-09-29-repaint-geometry'
PRIOR=ROOT / 'bench/results/2026-09-29-repaint-scenes/budget.json'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(report):
    for n,sha in report['input_sha256'].items():
        if digest(ROOT / n)!=sha:raise ValueError('geometry input drift '+n)
    for n,sha in report['output_sha256'].items():
        if digest(WORK / n)!=sha:raise ValueError('geometry build drift '+n)

def whole_links():
    links={}
    for name,cfg,target in (('normal','8502-bootstrap.cfg','build/8502/udeks-8502.bin'),
                            ('panic','8502-panic-probe.cfg','build/8502/udeks-8502-panic-probe.bin')):
        dry=subprocess.check_output(['make','-Bn',target],cwd=ROOT,text=True)
        command=link_command(dry.replace('cfg/8502-panic-probe.cfg','cfg/8502-bootstrap.cfg'))
        seen={};libraries={}
        for variant in ('baseline','replacement'):
            directory=WORK / name / variant;directory.mkdir(parents=True,exist_ok=True)
            config=directory / 'isolated.cfg'
            config.write_text(isolated_config((ROOT / 'cfg' / cfg).read_text(),directory))
            link=list(command);link[link.index('-C')+1]=str(config)
            link[link.index('-m')+1]=str(directory / 'kernel.map')
            link[link.index('-o')+1]=str(directory / 'kernel.bin')
            if variant=='replacement':
                link[link.index('build/8502/window_manager.o')]=str(WORK / 'replacement.o')
                link += [str(WORK / n) for n in ('damage.o','receipt.o','binding.o')]
            subprocess.run(link,cwd=ROOT,check=True)
            table=(directory / 'kernel.map').read_text()
            seen[variant]=segments(table);libraries[variant]=library_inventory(table)
        baseline=WORK / name / 'baseline'
        if (baseline / 'kernel.bin').read_bytes()!=(ROOT / target).read_bytes() or \
           seen['baseline']!=segments((ROOT / target.replace('.bin','.map')).read_text()):
            raise ValueError('isolated baseline is not the accepted kernel')
        old,new=seen['baseline'],seen['replacement']
        fixed=set(old)-{'CODE','RODATA','DATA','BSS','VICSHADOW'}
        if set(old)!=set(new) or any(old[n]!=new[n] for n in fixed):
            raise ValueError('fixed geometry placement/state changed')
        if any(old[n]['size']!=new[n]['size'] for n in ('RODATA','DATA','BSS','VICSHADOW')):
            raise ValueError('replacement gained hidden data/state')
        library_delta={}
        for provider,sign in ((libraries['replacement'],1),(libraries['baseline'],-1)):
            for module in provider.values():
                for seg,size in module.items():library_delta[seg]=library_delta.get(seg,0)+sign*size
        if any(v for s,v in library_delta.items() if s!='CODE'):
            raise ValueError('helper closure gained mutable state')
        links[name]={'baseline':old,'replacement':new,'code_growth':new['CODE']['size']-old['CODE']['size'],
                     'library_segment_delta':library_delta,'added_helpers':sorted(set(libraries['replacement'])-set(libraries['baseline'])),
                     'removed_helpers':sorted(set(libraries['baseline'])-set(libraries['replacement'])),
                     'input_sha256':{str(p.relative_to(ROOT)):digest(p) for p in
                        [*[ROOT / token for token in command if token.endswith('.o')],ROOT / target,ROOT / target.replace('.bin','.map')]}}
    return links

def candidate(text):
    for name in ('damage_set','damage_add'):
        if text.count('static void '+name+'(')!=1:
            raise ValueError('damage linkage seam changed '+name)
        old=function(text,name)
        declaration='void '+name+'(const struct udeks_window *window);\n'
        if text.count(old)!=1:raise ValueError('damage seam changed '+name)
        text=text.replace(old,declaration)
    for field,typ in (('damage_left','unsigned int'),('damage_top','unsigned char'),
                      ('damage_right','unsigned int'),('damage_bottom','unsigned char')):
        old='static '+typ+' '+field+';'
        if text.count(old)!=1:raise ValueError('damage field ownership changed '+field)
        text=text.replace(old,typ+' '+field+';')
    return text

def build():
    WORK.mkdir(parents=True,exist_ok=True)
    for directory in (PRIOR.parent,ROOT / 'bench/artifacts/2026-09-29-repaint-scenes'):
        for line in (directory / 'SHA256SUMS').read_text().splitlines():
            sha,n=line.split('  ',1)
            if digest(directory / n)!=sha:raise ValueError('prior scene evidence changed')
    base=raster.compact_source(raster.SOURCE.read_text())+'\n'+scenes.frontend((ROOT / 'bench/window-repaint-frontend/frontend.inc').read_text())
    old=scenes.WORK
    try:
        scenes.WORK=WORK
        original=scenes.compile_c('original',base)
        replacement=scenes.compile_c('replacement',candidate(base))
        probe=scenes.compile_c('probe',(SOURCE / 'probe.c').read_text())
    finally:scenes.WORK=old
    subprocess.run(['ca65','-l',str(WORK / 'damage.lst'),'-o',str(WORK / 'damage.o'),str(SOURCE / 'damage.s')],check=True)
    asm=object_sizes(WORK / 'damage.o')
    if any(asm.get(n,0) for n in ('BSS','DATA','HIGHBSS','ZEROPAGE','RODATA')):
        raise ValueError('geometry assembly allocated mutable/data state')
    removed=sum(original['functions']['_'+n]['size'] for n in ('damage_set','damage_add'))
    total_delta=replacement['segments']['CODE']+asm['CODE']-original['segments']['CODE']
    subprocess.run(['ca65','-o',str(WORK / 'startup.o'),str(SOURCE / 'startup.s')],check=True)
    subprocess.run(['cl65','-t','none','-C',str(ROOT / 'bench/window-repaint-raster/probe.cfg'),
        '-m',str(WORK / 'probe.map'),'-o',str(WORK / 'probe.bin'),
        *[str(WORK / (n+'.o')) for n in ('startup','probe','damage')]],check=True)
    (WORK / 'probe.prg').write_bytes(b'\x00\x20'+(WORK / 'probe.bin').read_bytes())
    archive=ROOT / 'bench/artifacts/2026-09-29-repaint-raster/build'
    for n in ('receipt.o','binding.o'):shutil.copy2(archive / n,WORK / n)
    links=whole_links()
    if len({v['code_growth'] for v in links.values()})!=1:raise ValueError('normal/panic geometry growth differs')
    if links['normal']['code_growth']>=1012:raise ValueError('geometry did not recover resident CODE')
    report={'scope':'UNBOOTABLE isolated geometry sizing + standalone 8502 arithmetic proof; not installed, no delivery/admission/NMI/provider qualification',
        'objects':{'original':original,'replacement':replacement,'assembly':asm,'probe':probe},'links':links,
        'budget':{'removed_C':removed,'asm_CODE':asm['CODE'],
            'other_compiler_delta':replacement['segments']['CODE']-original['segments']['CODE']+removed,
            'net_object_CODE_saved':-total_delta,'full_link_CODE_growth':links['normal']['code_growth'],
            'resident_growth_recovered':1012-links['normal']['code_growth'],
            'component':2371,'prior_allowance':2113,'provisional_remaining_shortfall':2371-(2113+1012-links['normal']['code_growth']),
            'scope':'lower bound before actual callers/delivery/admission/NMI/providers/teardown; damage bodies optimized, NOT retired'},
        'native':{'sha256':digest(WORK / 'probe.prg'),'cases':100,'scope':'real ASM vs independent C arithmetic; standalone, not actual manager call sites'},
        'toolchain':{n:subprocess.check_output([n,'--version'],stderr=subprocess.STDOUT,text=True).strip() for n in ('cc65','ca65','ld65','cl65')}}
    if report['budget']['resident_growth_recovered']!=81 or report['budget']['provisional_remaining_shortfall']!=177:
        raise ValueError('unreviewed geometry accounting change')
    inputs=[Path(__file__),PRIOR,PRIOR.parent / 'SHA256SUMS',ROOT / 'bench/artifacts/2026-09-29-repaint-scenes/SHA256SUMS',
        ROOT / 'tools/window_repaint_scenes.py',ROOT / 'tools/window_repaint_raster.py',ROOT / 'tools/window_repaint_compact.py',
        ROOT / 'tools/graphics_raster_link_audit.py',ROOT / 'tools/graphics_span_bench.py',ROOT / 'tools/graphics_raster_bench_build.py',
        ROOT / 'tools/vice_capture.py',ROOT / 'tools/1986_raster_bench.c',ROOT / 'tools/1986_input_smoke_build.py',
        ROOT / 'tools/graphics_raster_bench_run.py',ROOT / 'src/services/window/window_manager_cached.c',
        ROOT / 'Makefile',ROOT / 'mk/toolchain.mk',ROOT / 'cfg/8502-bootstrap.cfg',ROOT / 'cfg/8502-panic-probe.cfg',
        ROOT / 'tests/test_window_repaint_geometry.py',ROOT / 'bench/artifacts/2026-09-29-repaint-raster/build/receipt.o',
        ROOT / 'tests/test_window_repaint_geometry_evidence.py',
        ROOT / 'bench/artifacts/2026-09-29-repaint-raster/build/binding.o']+list(SOURCE.iterdir())
    report['input_sha256']={str(p.relative_to(ROOT)):digest(p) for p in inputs}
    for link in links.values():report['input_sha256'].update(link['input_sha256'])
    report['output_sha256']={str(p.relative_to(WORK)):digest(p) for p in sorted(WORK.rglob('*')) if p.is_file()
        and p.name not in ('budget.json','1986.bin','vice.bin','1986-runner')}
    (WORK / 'budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'removed_C':removed,'asm_CODE':asm['CODE'],'other_compiler_delta':replacement['segments']['CODE']-original['segments']['CODE']+removed,
        'net_CODE_saved':-total_delta,'new_mutable_segments':{n:asm.get(n,0) for n in ('BSS','DATA','HIGHBSS','ZEROPAGE')},
        'probe_CODE':probe['segments']['CODE'],'full_link_CODE_growth':links['normal']['code_growth'],
        'provisional_remaining_shortfall':report['budget']['provisional_remaining_shortfall']},indent=2))

def decode(data):
    if len(data)!=8096 or data[:6]!=b'DGEO\x01\x02' or data[6]!=0 or data[7]!=100 or any(data[8:16]):
        raise ValueError('incomplete/failed damage geometry record')
    return {'cases':100,'damage_set_code_removed':87,'damage_add_code_removed':163}

def run(engine,emulator):
    from graphics_raster_bench_run import emulator_provenance
    report=json.loads((WORK / 'budget.json').read_text());verify(report)
    RESULT.mkdir(parents=True,exist_ok=True)
    if engine=='1986':
        sources=importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
        provenance=emulator_provenance(emulator,sources)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
        runner=WORK / '1986-runner'
        subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator / 'src'),str(ROOT / 'tools/1986_raster_bench.c'),
            *map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
        command=[str(runner),str(WORK / 'probe.prg'),str(RESULT / '1986.bin'),'DGEO']
    else:
        provenance=subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True)
        command=['python3',str(ROOT / 'tools/vice_capture.py'),str(WORK / 'probe.prg'),str(RESULT / 'vice.bin'),
            '--entry','0x2000','--raw-load','--result-address','0x7fc0','--result-size','8096','--state-offset','5','--timeout','40']
    subprocess.run(command,check=True)
    raw=(RESULT / (engine+'.bin')).read_bytes();decoded=decode(raw)
    verify(report)
    if engine=='1986' and emulator_provenance(emulator,sources)!=provenance:raise ValueError('emulator drift')
    (RESULT / (engine+'.json')).write_text(json.dumps({'decoded':decoded,'raw_sha256':hashlib.sha256(raw).hexdigest(),
        'native_sha256':report['native']['sha256'],'build_report_sha256':digest(WORK / 'budget.json'),
        'provenance':provenance},indent=2)+'\n')
    print(json.dumps(decoded,indent=2))

def preserve():
    report=json.loads((WORK / 'budget.json').read_text());verify(report)
    for engine in ('1986','vice'):
        run=json.loads((RESULT / (engine+'.json')).read_text());data=(RESULT / (engine+'.bin')).read_bytes()
        if run['decoded']!=decode(data) or run['raw_sha256']!=hashlib.sha256(data).hexdigest() or \
           run['native_sha256']!=report['native']['sha256'] or run['build_report_sha256']!=digest(WORK / 'budget.json'):
            raise ValueError('geometry run/report/program mismatch')
    art=ROOT / 'bench/artifacts' / NAME;out=ROOT / 'bench/results' / NAME
    if art.exists() or out.exists():raise ValueError('refusing to overwrite evidence')
    for prefix,paths,base in (('inputs',report['input_sha256'],ROOT),('build',report['output_sha256'],WORK)):
        for n in paths:
            p=art / prefix / n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(base / n,p)
    out.mkdir(parents=True);shutil.copy2(WORK / 'budget.json',out / 'budget.json')
    for engine in ('1986','vice'):
        for ext in ('.bin','.json'):shutil.copy2(RESULT / (engine+ext),out / (engine+ext))
    for d in (art,out):
        (d / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(d)}\n' for p in sorted(d.rglob('*')) if p.is_file()))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',default='build',choices=('build','decode','run','preserve'))
    parser.add_argument('record',nargs='?',type=Path)
    parser.add_argument('--engine',choices=('1986','vice'))
    parser.add_argument('--emulator-root',type=Path,default=Path('/var/home/salvogendut/Dev/1986'))
    args=parser.parse_args()
    if args.action=='build':build()
    elif args.action=='decode':print(json.dumps(decode(args.record.read_bytes()),indent=2))
    elif args.action=='run':
        if not args.engine:parser.error('run needs --engine')
        run(args.engine,args.emulator_root)
    else:preserve()

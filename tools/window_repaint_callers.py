#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit actual repaint call sites and size an uninstalled request marshaller."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from graphics_raster_link_audit import link_command, segments
from window_repaint_compact import isolated_config, library_inventory
from graphics_span_bench import object_sizes
from placement_audit import parse_map
import window_repaint_scenes as scenes

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT / 'build/window-repaint-callers'
SOURCE=ROOT / 'bench/window-repaint-callers'
PRIOR=ROOT / 'bench/results/2026-09-29-repaint-geometry/budget.json'
GEOM=ROOT / 'bench/artifacts/2026-09-29-repaint-geometry'
NAME='2026-09-29-repaint-callers'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def function(text,name):
    matches=list(re.finditer(r'(?m)^(?:static )?(?:unsigned char|void)\s+(?:__fastcall__\s+)?'+re.escape(name)+r'\([^{}]*\)\n\{',text))
    if len(matches)!=1:raise ValueError('ambiguous manager function '+name)
    start=matches[0].end();depth=1;end=start
    while depth and end<len(text):
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    if depth:raise ValueError('unterminated manager function '+name)
    return text[start:end-1]

def source_audit(manager,window,xclock,xwave):
    calls={n:len(re.findall(r'\b'+n+r'\s*\(',manager))-(2 if n=='paint_window_damage' else 1) for n in
        ('compose_damage','paint_window_damage','damage_set','damage_add','cache_paint_image')}
    if calls!={'compose_damage':10,'paint_window_damage':1,'damage_set':7,
              'damage_add':2,'cache_paint_image':2}:
        raise ValueError('actual manager call graph changed; review all callers')
    callbacks=len(re.findall(r'window->paint\s*\(\s*handle\s*\)',manager))
    if callbacks!=2 or 'typedef void (*udeks_window_paint_fn)' not in window or \
       'UDEKS_WINDOW_BUSY' in window:
        raise ValueError('painter/deferred-return contract changed')
    if 'while (point_offset < draw_offset)' not in function(xwave,'paint_wave'):
        raise ValueError('xwave full callback changed; remeasure provider')
    if 'static void paint_clock(unsigned char handle)' not in xclock:
        raise ValueError('xclock callback changed; remeasure provider')
    order={
        'create':('window->flags =','damage_set(window);','compose_damage(UDEKS_WINDOW_NONE);'),
        'destroy':('damage_set(window);','window->active = 0;','compose_damage(UDEKS_WINDOW_NONE);','close(handle);'),
        'finish_drag':('damage_set(window);','window->x = drag_x;','damage_add(window);','compose_damage(UDEKS_WINDOW_NONE);'),
        'repaint':('damage_set(window);','window->paint(handle);','cache_paint_image(cache_owner);'),
    }
    bodies={alias:function(manager,name) for alias,name in
        (('create','udeks_window_create'),('destroy','udeks_window_destroy'),
         ('finish_drag','finish_drag'),('repaint','udeks_window_repaint'))}
    for alias,markers in order.items():
        body=bodies[alias];positions=[body.find(marker) for marker in markers]
        if -1 in positions or positions!=sorted(positions):
            # Some branches are not linearly ordered by source position; review
            # deliberately rather than inferring a safe mutation fence.
            if alias!='finish_drag' or positions[:3]!=sorted(positions[:3]) or positions[3]<0:
                raise ValueError('manager mutation/callback ordering changed '+alias)
    return {'synchronous_compositions':calls['compose_damage'],'paint_callback_calls':callbacks,
            'damage_set_calls':calls['damage_set'],'damage_add_calls':calls['damage_add'],
            'cache_paint_image_calls':calls['cache_paint_image'],
            'public_paint_statuses':['OK','INVALID','FULL'],
            'xwave_callback':'whole prefix loop, not a progress-returning provider',
            'xclock_callback':'void full painter, not a progress-returning provider',
            'ordering':'create/destroy/drag/repaint mutation and callback sites require explicit pre-edit fence and deferred completion'}

def verify(report):
    for n,sha in report['input_sha256'].items():
        if digest(ROOT / n)!=sha:raise ValueError('caller input drift '+n)
    for n,sha in report['output_sha256'].items():
        if digest(WORK / n)!=sha:raise ValueError('caller output drift '+n)

def build():
    WORK.mkdir(parents=True,exist_ok=True)
    for d in (PRIOR.parent,GEOM):
        for line in (d / 'SHA256SUMS').read_text().splitlines():
            sha,n=line.split('  ',1)
            if digest(d / n)!=sha:raise ValueError('geometry evidence changed')
    manager=(ROOT / 'src/services/window/window_manager_cached.c').read_text()
    window=(ROOT / 'include/udeks/window.h').read_text()
    audit=source_audit(manager,window,(ROOT / 'src/apps/xclock.c').read_text(),
                       (ROOT / 'src/apps/xwave.c').read_text())
    old=scenes.WORK
    try:scenes.WORK=WORK;obj=scenes.compile_c('control',(SOURCE / 'control.c').read_text())
    finally:scenes.WORK=old
    if obj['segments']['CODE']!=78 or any(obj['segments'].get(s,0) for s in ('BSS','DATA','ZEROPAGE','HIGHBSS','RODATA')):
        raise ValueError('marshalling object code/state changed')
    for n in ('replacement.o','damage.o','receipt.o','binding.o'):
        shutil.copy2(GEOM / 'build' / n,WORK / n)
    prior=json.loads(PRIOR.read_text());links={}
    for name,cfg,target in (('normal','8502-bootstrap.cfg','build/8502/udeks-8502.bin'),
                            ('panic','8502-panic-probe.cfg','build/8502/udeks-8502-panic-probe.bin')):
        dry=subprocess.check_output(['make','-Bn',target],cwd=ROOT,text=True)
        command=link_command(dry.replace('cfg/8502-panic-probe.cfg','cfg/8502-bootstrap.cfg'))
        directory=WORK / name;directory.mkdir(parents=True,exist_ok=True)
        config=directory / 'isolated.cfg'
        config.write_text(isolated_config((ROOT / 'cfg' / cfg).read_text(),directory))
        link=list(command);link[link.index('-C')+1]=str(config)
        link[link.index('-m')+1]=str(directory / 'kernel.map')
        link[link.index('-o')+1]=str(directory / 'kernel.bin')
        link[link.index('build/8502/window_manager.o')]=str(WORK / 'replacement.o')
        link += [str(WORK / (n+'.o')) for n in ('damage','receipt','binding','control')]
        subprocess.run(link,cwd=ROOT,check=True)
        table=(directory / 'kernel.map').read_text()
        seg=segments(table);oldseg=prior['links'][name]['replacement']
        for s in set(oldseg)-{'CODE','RODATA','DATA','BSS','VICSHADOW'}:
            if seg[s]!=oldseg[s]:raise ValueError('fixed state/placement changed '+s)
        for s in ('RODATA','DATA','BSS','VICSHADOW'):
            if seg[s]['size']!=oldseg[s]['size']:raise ValueError('unbudgeted data/state '+s)
        delta=seg['CODE']['size']-oldseg['CODE']['size']
        if delta!=78:raise ValueError('marshaller/link helper closure not fully charged')
        modules,_=parse_map(table)
        libs=library_inventory(table)
        if libs!=library_inventory((GEOM / 'build' / name / 'replacement' / 'kernel.map').read_text()):
            raise ValueError('marshaller pulled new runtime helper')
        links[name]={'segments':seg,'code_delta_over_geometry':delta,'code_growth_over_production':seg['CODE']['size']-prior['links'][name]['baseline']['CODE']['size'],
                     'helper_modules':libs,'baseline_accepted_sha256':digest(ROOT / target),
                     'input_sha256':{str(p.relative_to(ROOT)):digest(p) for p in
                       [*[ROOT / token for token in command if token.endswith('.o')],ROOT / target,ROOT / target.replace('.bin','.map')]}}
    if {v['code_growth_over_production'] for v in links.values()}!={1009}:
        raise ValueError('full-link caller floor changed')
    report={'scope':'UNBOOTABLE isolated shared marshalling cost and source-derived real-call-site audit; no installed caller/provider/admission/NMI or app ABI change',
            'audit':audit,'object':obj,'links':links,
            'budget':{'previous_component':2371,'previous_allowance_with_geometry':2194,
                      'marshaller_CODE':78,'measured_floor':255,
                      'scope':'lower bound BEFORE a single caller, provider, admission/lease, delivery, busy/teardown or NMI cost'},
            'toolchain':{n:subprocess.check_output([n,'--version'],stderr=subprocess.STDOUT,text=True).strip() for n in ('cc65','ca65','ld65','cl65')}}
    inputs=[Path(__file__),PRIOR,PRIOR.parent / 'SHA256SUMS',GEOM / 'SHA256SUMS',
        SOURCE / 'control.c',ROOT / 'src/services/window/window_manager_cached.c',ROOT / 'src/apps/xclock.c',
        ROOT / 'src/apps/xwave.c',ROOT / 'include/udeks/window.h',ROOT / 'include/udeks/repaint_lane.h',
        ROOT / 'tools/window_repaint_scenes.py',ROOT / 'tools/window_repaint_geometry.py',
        ROOT / 'tools/window_repaint_compact.py',ROOT / 'tools/graphics_raster_link_audit.py',
        ROOT / 'tools/graphics_span_bench.py',ROOT / 'tools/placement_audit.py',
        ROOT / 'Makefile',ROOT / 'mk/toolchain.mk',ROOT / 'cfg/8502-bootstrap.cfg',ROOT / 'cfg/8502-panic-probe.cfg',
        ROOT / 'tests/test_window_repaint_callers.py',ROOT / 'tests/test_window_repaint_callers_evidence.py']
    inputs += [GEOM / 'build' / n for n in ('replacement.o','damage.o','receipt.o','binding.o')]
    report['input_sha256']={str(p.relative_to(ROOT)):digest(p) for p in inputs}
    for link in links.values():report['input_sha256'].update(link['input_sha256'])
    report['output_sha256']={str(p.relative_to(WORK)):digest(p) for p in sorted(WORK.rglob('*')) if p.is_file() and p.name!='budget.json'}
    (WORK / 'budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'audit':audit,'budget':report['budget']},indent=2))

def preserve():
    report=json.loads((WORK / 'budget.json').read_text());verify(report)
    art=ROOT / 'bench/artifacts' / NAME;out=ROOT / 'bench/results' / NAME
    if art.exists() or out.exists():raise ValueError('refusing to overwrite caller evidence')
    for prefix,paths,base in (('inputs',report['input_sha256'],ROOT),('build',report['output_sha256'],WORK)):
        for n in paths:
            p=art / prefix / n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(base / n,p)
    out.mkdir(parents=True);shutil.copy2(WORK / 'budget.json',out / 'budget.json')
    for d in (art,out):
        (d / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(d)}\n' for p in sorted(d.rglob('*')) if p.is_file()))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',default='build',choices=('build','preserve'))
    args=parser.parse_args()
    if args.action=='build':build()
    else:preserve()

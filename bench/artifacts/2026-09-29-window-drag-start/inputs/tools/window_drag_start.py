#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure a deferred-background drag prototype; not enabled in normal builds."""
import argparse
import json
import subprocess
import re
import shutil
from pathlib import Path
from window_cache_partial_manager import candidate as parent
from window_cache_manager import BASE,replace
from graphics_span_bench import object_sizes
import window_cache_live as live
import window_cache_partial as partial
from window_cache_occlusion import native_profile

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/bench/drag-start-prototype'
NAME='2026-09-29-window-drag-start'


def candidate(source):
    text=parent(source)
    text=replace(text,'''    damage_set(window);
    compose_damage(handle);
    udeks_vic_bitmap_outline_toggle(''','''    damage_set(window);
    /* Erase content without invoking lower applications on the button path.
     * The old/new union is fully recomposed by finish_drag on release. */
    compose_damage(255u);
    udeks_vic_bitmap_outline_toggle(''')
    text=replace(text,'(drag_mode & CACHED_MOVE) == 0 || skip_handle != cache_owner',
        '(drag_mode & CACHED_MOVE) == 0 || (skip_handle != cache_owner && skip_handle != 255u)')
    return replace(text,'    for (rank = 1u; rank <= active_count; ++rank) {',
        '''    /* Private erase-only mode: no client callbacks until release. */
    for (rank = 1u; skip_handle != 255u && rank <= active_count; ++rank) {''')


def measure():
    WORK.mkdir(parents=True,exist_ok=True)
    values={}
    for name,transform in (('before',parent),('deferred',candidate)):
        path=WORK/(name+'.c');path.write_text(transform(BASE.read_text()))
        subprocess.run(['cl65','-t','none','--cpu','6502','--standard','c99','-Oirs',
            '-I',str(ROOT/'include'),'-c','-o',str(WORK/(name+'.o')),str(path)],check=True)
        values[name]=object_sizes(WORK/(name+'.o'))
    (WORK/'sizes.json').write_text(json.dumps(values,indent=2)+'\n')
    print(json.dumps(values,indent=2))


def configure():
    live.WORK=ROOT/'build/window-drag-start'
    live.REPO=live.WORK/'repo';live.NAME=NAME
    live.PROOF=ROOT/'bench/artifacts'/partial.NAME
    live.MODULE_REL='build/bench/window-cache-partial/module.bin'
    live.LOADER_REL='build/bench/window-cache-partial/acceptance/loader.inc'
    live.candidate=candidate


def inputs():
    return tuple(ROOT/name for name in ('tools/window_drag_start.py',
        'tools/window_drag_latency.py',
        'tools/window_cache_partial_manager.py','tools/window_cache_occlusion.py',
        'tools/window_cache_repaint.py','tests/test_window_drag_start.py'))


def preserve():
    configure()
    runs={};values={}
    for variant in ('partial','deferred'):
        directory=ROOT/'build/drag-start-latency'/variant
        run=json.loads((directory/'run.json').read_text());runs[variant]=run
        for name,sha in run['input_sha256'].items():
            if live.digest(ROOT/name)!=sha:raise ValueError('latency input drift '+name)
        for name,key in (('native.c','source_sha256'),('native','runner_sha256')):
            if live.digest(directory/name)!=run[key]:raise ValueError('latency runner drift')
        values[variant]={}
        for fmt,sha in run['log_sha256'].items():
            path=directory/(fmt+'.log')
            if live.digest(path)!=sha:raise ValueError('latency log drift')
            text=path.read_text()
            found=re.findall(r'^(clock drag start|overlap clock drag start): frames=(\d+)$',text,re.M)
            if len(found)!=2 or 'PASS: native clock-only/overlap drag-start timing and shutdown' not in text:
                raise ValueError('incomplete clock timing')
            values[variant][fmt]={name:int(frames) for name,frames in found}
    if runs['partial']['provenance']!=runs['deferred']['provenance']:
        raise ValueError('latency emulator provenance differs')
    for fmt in ('d71','d64'):
        before=values['partial'][fmt]['overlap clock drag start']
        after=values['deferred'][fmt]['overlap clock drag start']
        if not 0<after<=30 or after>=before:raise ValueError('clock latency did not improve')
    clean=json.loads((live.WORK/'clean-build.json').read_text())
    if clean['before']!=clean['after'] or clean['after']!=live.verify_build()['disk_sha256'] or \
       clean['report_sha256']!=live.digest(live.WORK/'report.json'):
        raise ValueError('clean-build evidence drift')
    live.preserve()
    result=ROOT/'bench/results'/NAME;artifact=ROOT/'bench/artifacts'/NAME
    (result/'drag-latency.json').write_text(json.dumps(values,indent=2)+'\n')
    shutil.copy2(live.WORK/'clean-build.json',result/'clean-build.json')
    for variant in runs:
        directory=ROOT/'build/drag-start-latency'/variant
        for name in ('run.json','d71.log','d64.log'):
            target=result/'latency'/variant/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(directory/name,target)
        for name in ('native.c','native'):
            target=artifact/'latency'/variant/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(directory/name,target)
    for directory in (result,artifact):
        paths=sorted(p for p in directory.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
        (directory/'SHA256SUMS').write_text(''.join(f'{live.digest(p)}  {p.relative_to(directory)}\n' for p in paths))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('measure','build','1986','vice','clean','preserve'))
    args=parser.parse_args()
    if args.action=='measure':measure()
    else:
        configure()
        if args.action=='build':live.build(extra_inputs=inputs())
        elif args.action=='1986':live.probe_native(native_profile)
        elif args.action=='vice':live.probe_vice()
        elif args.action=='clean':
            before=live.verify_build()['disk_sha256']
            expected=ROOT/'build/window-drag-start/repo'
            if live.REPO.resolve()!=expected.resolve() or not (expected/'Makefile').is_file():
                raise ValueError('unexpected private clean target')
            subprocess.run(['make','clean'],cwd=expected,check=True)
            live.build(extra_inputs=inputs())
            after=live.verify_build()['disk_sha256']
            if before!=after:raise ValueError('private clean changed disk bytes')
            (live.WORK/'clean-build.json').write_text(json.dumps({'before':before,'after':after,
                'report_sha256':live.digest(live.WORK/'report.json')},indent=2)+'\n')
        else:preserve()

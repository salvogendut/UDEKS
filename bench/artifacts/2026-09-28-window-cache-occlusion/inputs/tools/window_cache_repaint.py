#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure/fix repeated page commits on separate live cache test disks."""
import argparse
import json
import re
import shutil
import statistics
from pathlib import Path
import window_cache_live as live
from window_cache_manager import candidate, replace
from gen_capability_imports import map_exports

ROOT=live.ROOT
WORK=ROOT / 'build/window-cache-repaint'
PREFIX='2026-09-28-window-cache-repaint'


def tiled(source):
    text=candidate(source)
    text=replace(text,'#define CACHED_MOVE 0x80u', '''#define CACHED_MOVE 0x80u
#ifdef UDEKS_CACHE_MANAGER_HOST_TEST
extern unsigned char manager_test_row_offset;
#define CACHE_ROW_OFFSET manager_test_row_offset
#else
/* Last successful STEP's bitmap offset: low three bits are its scanline.
 * No intervening gateway/user call before this read; IRQ/NMI don't use it. */
#define CACHE_ROW_OFFSET (*(volatile unsigned char *)0xF780u)
#endif''')
    return replace(text,'''        } while (--budget != 0 && cache_phase == phase);
        if (phase == UDEKS_CACHE_PASTING) udeks_vic_bitmap_commit();''','''        } while (--budget != 0 && cache_phase == phase &&
            (phase != UDEKS_CACHE_PASTING || (CACHE_ROW_OFFSET & 7u) != 7u));
        /* Keep the four-row input budget. Finish a physical eight-scanline
         * bitmap band before committing its pages; always flush final/error. */
        if (phase == UDEKS_CACHE_PASTING &&
            (cache_phase != UDEKS_CACHE_PASTING || (CACHE_ROW_OFFSET & 7u) == 7u))
            udeks_vic_bitmap_commit();''')


def profile(code):
    symbols=map_exports((live.REPO / 'build/8502/udeks-8502.map').read_text())
    text=''.join(f'#define {macro} 0x{symbols[name][0]:04x}u\n' for macro,name in (
        ('PROFILE_PAGE','_udeks_vic_bitmap_commit_page'),('PROFILE_DISABLE','_udeks_vic_graphics_disable')))
    text+=(ROOT / 'bench/window-cache-manager/profile.inc').read_text()
    code=replace(code,'static void frames(unsigned count) { while (count--) c128_frame(machine); }',text)
    code=replace(code,'        unsigned delay=drag_release(before),start=c128_frame_count;',
        '        profile_begin();\n        unsigned delay=drag_release(before),start=c128_frame_count;\n        profile_stage=2;')
    code=replace(code,'        pixel_oracle();\n        require(word(0xF270)==paints',
        '        profile_end(i);\n        pixel_oracle();\n        require(word(0xF270)==paints')
    # Same Ctrl+C stimulus as the reference, now also publish elapsed frames.
    code=replace(code,'    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);',
        '    unsigned cancel_start=c128_frame_count;\n    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);')
    code=replace(code,'    require(byte(0xF225)==3,"cancellation killed background clock");',
        '    printf("cancel profile: frames=%u\\n",c128_frame_count-cancel_start);\n    require(byte(0xF225)==3,"cancellation killed background clock");')
    return code


def configure(variant):
    live.WORK=WORK / variant;live.REPO=live.WORK / 'repo';live.NAME=PREFIX+'-'+variant
    live.candidate=tiled if variant=='tiled' else candidate


def measurements(log):
    moves=[{'move':int(i),'x':int(x),'y':int(y),'release':int(r),'paste':int(p)}
        for i,x,y,r,p in re.findall(r'^cache move (\d+): x=(\d+) y=(\d+) release=(\d+) paste=(\d+) pixels=OK$',log,re.M)]
    pages=[{'move':int(i),'stage':int(s),'calls':int(c),'unique':int(u),'cycles':int(t)}
        for i,s,c,u,t in re.findall(r'^page profile (\d+) stage=(\d+) calls=(\d+) unique=(\d+) cycles=(\d+)$',log,re.M)]
    cancel=re.findall(r'^cancel profile: frames=(\d+)$',log,re.M)
    clocks={int(i):int(p) for i,p in re.findall(r'^clock profile (\d+): paints=(\d+)$',log,re.M)}
    shutdown=[{'raster':int(r),'target':int(t)} for r,t in re.findall(
        r'^shutdown profile: raster=(\d+) target=(\d+)$',log,re.M)]
    if len(moves)!=16 or len(pages)!=32 or len(cancel)!=1 or set(clocks)!=set(range(16)) or not shutdown or any(s['target']>=256 for s in shutdown):
        raise ValueError('incomplete profiling qualification')
    if [m['move'] for m in moves]!=list(range(16)) or {(p['move'],p['stage']) for p in pages}!={(m,s) for m in range(16) for s in (1,2)}:
        raise ValueError('duplicate/missing move profiles')
    paste=[p for p in pages if p['stage']==2]
    for move in moves:move['clock_paints']=clocks[move['move']]
    return {'moves':moves,'pages':pages,'cancel_frames':int(cancel[0]),'shutdown':shutdown,
        'median_paste_frames':statistics.median(m['paste'] for m in moves),
        'worst_paste_frames':max(m['paste'] for m in moves),
        'median_total_frames':statistics.median(m['paste']+m['release'] for m in moves),
        'median_paste_page_copies':statistics.median(p['calls'] for p in paste),
        'median_paste_copy_cycles':statistics.median(p['cycles'] for p in paste)}


def compare():
    values={}
    for variant in ('baseline','tiled'):
        configure(variant);live.verify_build()
        binding=json.loads((live.WORK / '1986-run.json').read_text())
        if binding['report_sha256']!=live.digest(live.WORK / 'report.json'):raise ValueError('stale native run')
        values[variant]={}
        for fmt in ('d71','d64'):
            log=live.WORK / f'1986-{fmt}.log'
            if live.digest(log)!=binding['results'][fmt]['log_sha256']:raise ValueError('log drift')
            values[variant][fmt]=measurements(log.read_text())
    for fmt in ('d71','d64'):
        a,b=values['baseline'][fmt],values['tiled'][fmt]
        if [(v['x'],v['y']) for v in a['moves']]!=[(v['x'],v['y']) for v in b['moves']]:raise ValueError('geometry mismatch')
        for key in ('median_paste_frames','median_total_frames','median_paste_page_copies','median_paste_copy_cycles','cancel_frames'):
            if b[key]>=a[key]:raise ValueError('no measured improvement '+key)
    report={'scope':'read-only 1986 PC breakpoints; full frames resumed; native input, active clock/NMI; medians include clock repair',
        'values':values,'inputs_sha256':{str(p.relative_to(ROOT)):live.digest(p)
            for v in ('baseline','tiled') for p in (WORK / v / 'report.json',WORK / v / '1986-run.json',
                WORK / v / '1986-d71.log',WORK / v / '1986-d64.log')}}
    (WORK / 'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({v:{f:{k:r[k] for k in r if k.startswith('median_') or k in ('cancel_frames','worst_paste_frames')}
                           for f,r in fs.items()} for v,fs in values.items()},indent=2))


def preserve():
    comparison=WORK / 'comparison.json'
    data=json.loads(comparison.read_text())
    for name,sha in data['inputs_sha256'].items():
        if live.digest(ROOT / name)!=sha:raise ValueError('comparison binding drift')
    failure=live.WORK / 'failure'
    if failure.exists():
        for line in (failure / 'SHA256SUMS').read_text().splitlines():
            sha,name=line.split('  ',1)
            if live.digest(failure / name)!=sha:raise ValueError('failure evidence drift')
    live.preserve()
    # Keep the diagnosed original failure separate from the qualified runs.
    # Its own manifest covers original disk/kernel/runner; never copy the VSF.
    result=ROOT / 'bench/results' / live.NAME
    if failure.exists():shutil.copytree(failure,result / 'failure')
    shutil.copy2(comparison,result / 'comparison.json')
    paths=sorted(p for p in result.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    (result / 'SHA256SUMS').write_text(''.join(f'{live.digest(p)}  {p.relative_to(result)}\n' for p in paths))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant',choices=('baseline','tiled'))
    parser.add_argument('action',choices=('build','1986','vice','compare','preserve'))
    args=parser.parse_args();configure(args.variant)
    if args.action=='build':
        live.build((Path(__file__),ROOT / 'bench/window-cache-manager/profile.inc',
                    ROOT / 'bench/window-cache-manager/shutdown-snapshot.c',
                    ROOT / 'tests/test_window_cache_repaint.py'))
    elif args.action=='1986':live.probe_native(profile)
    else:{'vice':live.probe_vice,'compare':compare,'preserve':preserve}[args.action]()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build and qualify an isolated prefix-repair compositor; no normal mutation."""
import argparse
import json
import subprocess
from pathlib import Path
import window_cache_live as live
from window_cache_occlusion import native_profile, clock_measurements
import window_cache_partial as partial
from graphics_span_bench import object_sizes
from window_cache_occlusion import occluded
from window_cache_manager import BASE, replace

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/bench/window-cache-partial-manager'
NAME='2026-09-29-window-cache-partial-manager'


def candidate(source):
    text=occluded(source)
    # Clip calculations already provide a bounded top, bottom and right.
    # Reuse them for the private prefix operation, not a second renderer.
    old=text[text.index('static unsigned char set_damage_intersection('):
             text.index('static void draw_glyph(')].rstrip()
    new=replace(old,'    return 1;', '''    CACHE_PARTIAL_FIRST = top - y;
    CACHE_PARTIAL_END = bottom - y;
    CACHE_PARTIAL_WIDTH = right - x;
    return 1;''')
    text=replace(text,old,new)
    text=replace(text,'static unsigned char set_damage_intersection(','''#ifdef UDEKS_CACHE_MANAGER_HOST_TEST
extern unsigned char manager_partial_first, manager_partial_end;
extern unsigned int manager_partial_width;
#define CACHE_PARTIAL_FIRST manager_partial_first
#define CACHE_PARTIAL_END manager_partial_end
#define CACHE_PARTIAL_WIDTH manager_partial_width
#else
#define CACHE_PARTIAL_FIRST (*(volatile unsigned char *)0xF78Au)
#define CACHE_PARTIAL_END (*(volatile unsigned char *)0xF78Bu)
#define CACHE_PARTIAL_WIDTH (*(volatile unsigned int *)0xF78Cu)
#endif
static unsigned char set_damage_intersection(''')
    text=replace(text,'''    unsigned char paste = set_damage_intersection(
        cached->x, cached->y, cached->width, cached->height);''','    unsigned char paste;')
    text=replace(text,'''    if (paste == 0) cache_phase = UDEKS_CACHE_READY;
    else if (cache_request(handle, UDEKS_CACHE_COMMAND_PASTE) != UDEKS_CACHE_OK)''','''    /* Composition owns the shared VIC workspace. Prepare the prefix only
     * after callbacks/commits finish, immediately before the banked request. */
    paste = set_damage_intersection(cached->x, cached->y, cached->width, cached->height);
    udeks_vic_bitmap_reset_clip();
    if (paste == 0) cache_phase = UDEKS_CACHE_READY;
    else if (cache_request(handle, 6) != UDEKS_CACHE_OK)''')
    return text


def measure():
    WORK.mkdir(parents=True,exist_ok=True)
    source=candidate(BASE.read_text())
    variants={'baseline':occluded(BASE.read_text()),'partial':source}
    # Only register-storage experiments; do not alter ownership or algorithms.
    for name in ('left','right','top','bottom'):
        declaration=('unsigned int ' if name in ('left','right') else 'unsigned char ')+name+';'
        variants[name]=source.replace(declaration,'register '+declaration)
    report={}
    for name,text in variants.items():
        path=WORK/(name+'.c');path.write_text(text)
        subprocess.run(['cl65','-t','none','--cpu','6502','--standard','c99','-Oirs',
            '-I',str(ROOT/'include'),'-c','-o',str(WORK/(name+'.o')),str(path)],check=True)
        report[name]=object_sizes(WORK/(name+'.o'))
    (WORK/'sizes.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


def configure():
    global WORK
    WORK=ROOT/'build/window-cache-partial'
    live.WORK=WORK;live.REPO=WORK/'repo';live.NAME=NAME
    live.PROOF=ROOT/'bench/artifacts'/partial.NAME
    live.MODULE_REL='build/bench/window-cache-partial/module.bin'
    live.LOADER_REL='build/bench/window-cache-partial/acceptance/loader.inc'
    live.candidate=candidate


def build_inputs():
    return (Path(__file__),ROOT/'tools/window_cache_occlusion.py',
        ROOT/'tools/window_cache_repaint.py',ROOT/'tests/test_window_cache_partial_manager.py')


def clean_build():
    """Clean only this generated test repository; preserve the normal tree."""
    configure()
    report_path=WORK/'report.json'
    before=json.loads(report_path.read_text())['disk_sha256']
    for fmt,sha in before.items():
        if live.digest(WORK/f'udeks-cache.{fmt}')!=sha:raise ValueError('pre-clean disk drift')
    expected=ROOT/'build/window-cache-partial/repo'
    if live.REPO.resolve()!=expected.resolve() or not (expected/'Makefile').is_file():
        raise ValueError('unexpected private clean target')
    subprocess.run(['make','clean'],cwd=expected,check=True)
    live.build(extra_inputs=build_inputs())
    after=live.verify_build()['disk_sha256']
    if before!=after:raise ValueError('clean build changed disk bytes')
    (WORK/'clean-build.json').write_text(json.dumps({'scope':'full private make clean, parallel build, same disk bytes',
        'before':before,'after':after,'report_sha256':live.digest(report_path)},indent=2)+'\n')


def compare():
    """Compare only source-bound native evidence and complete canvas bytes."""
    configure();live.verify_build()
    native=json.loads((WORK/'1986-run.json').read_text())
    if native['report_sha256']!=live.digest(WORK/'report.json'):raise ValueError('stale native run')
    reference=ROOT/'bench/results/2026-09-28-window-cache-occlusion'
    original=json.loads((reference/'1986-run.json').read_text())
    if original['provenance']!=native['provenance']:raise ValueError('different emulator inputs')
    for line in (reference/'SHA256SUMS').read_text().splitlines():
        sha,name=line.split('  ',1)
        if live.digest(reference/name)!=sha:raise ValueError('reference drift')
    comparisons={};inputs={str((reference/'SHA256SUMS').relative_to(ROOT)):live.digest(reference/'SHA256SUMS')}
    for fmt in ('d71','d64'):
        old_log=reference/f'1986-{fmt}.log';new_log=WORK/f'1986-{fmt}.log'
        if live.digest(old_log)!=original['results'][fmt]['log_sha256'] or live.digest(new_log)!=native['results'][fmt]['log_sha256']:
            raise ValueError('native log mismatch')
        before=clock_measurements(old_log.read_text());after=clock_measurements(new_log.read_text())
        for case in range(3):
            values=[]
            for directory,binding in ((reference,original),(WORK,native)):
                for surface in ('shadow','bitmap'):
                    path=directory/f'1986-{fmt}-clock-{case}-{surface}.bin'
                    if live.digest(path)!=binding['raw_sha256'].get(path.name):raise ValueError('unbound pixels')
                    values.append(path.read_bytes());inputs[str(path.relative_to(ROOT))]=live.digest(path)
            if len(values[0])!=8000 or any(v!=values[0] for v in values):raise ValueError('clock canvas changed')
        if after[2]['frames']>=before[2]['frames'] or after[2]['pages']>=before[2]['pages']:
            raise ValueError('no complex-overlap improvement')
        comparisons[fmt]={'before':before,'after':after}
        for path in (old_log,new_log,WORK/'1986-run.json',WORK/'report.json'):
            inputs[str(path.relative_to(ROOT))]=live.digest(path)
    result={'scope':'same native mouse/date cases; complete clock canvases match saved occlusion candidate',
            'inputs_sha256':inputs,'values':comparisons}
    (WORK/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(comparisons,indent=2))


def preserve():
    configure()
    path=WORK/'comparison.json';data=json.loads(path.read_text())
    for name,sha in data['inputs_sha256'].items():
        if live.digest(ROOT/name)!=sha:raise ValueError('comparison input drift')
    clean_path=WORK/'clean-build.json';clean=json.loads(clean_path.read_text())
    if clean['report_sha256']!=live.digest(WORK/'report.json') or clean['before']!=clean['after'] or clean['after']!=live.verify_build()['disk_sha256']:
        raise ValueError('clean-build proof drift')
    live.preserve()
    import shutil
    directory=ROOT/'bench/results'/NAME
    shutil.copy2(path,directory/'comparison.json')
    shutil.copy2(clean_path,directory/'clean-build.json')
    files=sorted(p for p in directory.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    (directory/'SHA256SUMS').write_text(''.join(f'{live.digest(p)}  {p.relative_to(directory)}\n' for p in files))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('measure','build','clean','1986','vice','compare','preserve'))
    args=parser.parse_args()
    if args.action=='measure':measure()
    else:
        configure()
        if args.action=='build':live.build(extra_inputs=build_inputs())
        elif args.action=='clean':clean_build()
        elif args.action=='1986':live.probe_native(native_profile)
        elif args.action=='vice':live.probe_vice()
        elif args.action=='compare':compare()
        else:preserve()

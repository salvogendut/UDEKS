#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private resident raster replacement sizing, never packages a boot disk."""
import json
from pathlib import Path
import hashlib
import shutil
import subprocess
import re
import argparse
import importlib
import shlex
from graphics_raster_bench_build import function
from graphics_cache_placement import listing_functions
from graphics_span_bench import object_sizes
from window_repaint_compact import candidate, imports, isolated_config, library_inventory
from repaint_lane_budget import raster_source
from graphics_raster_link_audit import link_command, segments

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/window-repaint-raster'
SOURCE = ROOT / 'src/services/window/window_manager_cached.c'
NAME = '2026-09-29-repaint-raster'
CASES = ((0,0,16,18,0),(303,182,17,18,13),(0,0,48,48,1),
         (256,96,64,104,15),(150,96,168,104,13),(0,0,320,200,13),
         (10,10,100,100,13),(220,100,100,100,13))


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(case):
    """Independent old full-window geometry, not new row-fragment execution."""
    text = SOURCE.read_text().split('static const unsigned char title_glyphs[26][5] = {',1)[1].split('};',1)[0]
    glyphs = list(map(int,re.findall(r'\d+',text)))
    if len(glyphs) != 130: raise ValueError('glyph reference changed')
    image = bytearray(8000)
    x,y,w,h,flags = CASES[case]
    def pixel(a,b,black=True):
        if 0 <= a < 320 and 0 <= b < 200:
            at=(b&248)*40+(a&~7)+(b&7);mask=128>>(a&7)
            if black:image[at]|=mask
            else:image[at]&=255^mask
    def line(a,b,c,d):
        dx=abs(c-a);dy=-abs(d-b);sx=1 if a<c else -1;sy=1 if b<d else -1;err=dx+dy
        while True:
            pixel(a,b)
            if (a,b)==(c,d): break
            e=err*2
            if e>=dy:err+=dy;a+=sx
            if e<=dx:err+=dx;b+=sy
    def rectangle(a,b,width,height):
        line(a,b,a+width-1,b);line(a,b+height-1,a+width-1,b+height-1)
        line(a,b,a,b+height-1);line(a+width-1,b,a+width-1,b+height-1)
    rectangle(x,y,w,h);rectangle(x+2,y+2,w-4,h-4)
    height_text=(ROOT / 'include/udeks/window.h').read_text()
    title_height=int(re.search(r'#define\s+UDEKS_WINDOW_TITLE_HEIGHT\s+(\d+)u',height_text)[1])
    line(x+2,y+title_height,x+w-3,y+title_height)
    title = '' if case==0 else ('M'*96 if case==5 else 'aZ ? Xclock')
    at=x+4
    for ch in title:
        if at+3 > x+w-14: break
        ch=ch.upper()
        if 'A' <= ch <= 'Z':
            for row in range(5):
                bits=glyphs[(ord(ch)-65)*5+row]
                for col in range(3):
                    if bits & (4>>col):pixel(at+col,y+4+row)
        at+=4
    if flags & 4: # CLOSABLE
        a=x+w-12;rectangle(a,y+3,8,8)
        line(a+2,y+5,a+5,y+8);line(a+5,y+5,a+2,y+8)
    if flags & 8: # RESIZABLE
        right=x+w-5;bottom=y+h-5
        line(right-6,bottom,right,bottom-6);line(right-3,bottom,right,bottom-3)
    for yy in range(y+14,y+h-3):
        for xx in range(x+3,x+w-3):
            pixel(xx,yy,(xx*3+yy*5)%7 < 3)
    return bytes(image)


def checksum(image):
    low=0x57;high=0x13
    for byte in image:low=(low+byte)&255;high=(high+low)&255
    return low|(high<<8)


def native_build():
    import window_repaint_bank as bank
    from graphics_raster_bench_build import function
    proof = ROOT / 'bench/artifacts/2026-09-29-repaint-bank'
    for line in (proof / 'SHA256SUMS').read_text().splitlines():
        sha,name=line.split('  ',1)
        if digest(proof / name)!=sha:raise ValueError('qualified bank proof changed')
    shutil.copy2(proof / 'build/module-envelope.bin',WORK / 'module-envelope.bin')
    shutil.copy2(proof / 'build/launcher.s',WORK / 'launcher.s')
    driver=bank.diagnostic_driver((bank.OLD / 'driver.s').read_text())
    driver=driver.replace('_private_cache_policy_call','_private_repaint_policy_call').replace(
        'build/bench/window-repaint-bank/module-envelope.bin',str(WORK / 'module-envelope.bin'))
    (WORK / 'driver.s').write_text(driver)
    refs = [checksum(reference(i)) for i in range(8)]
    header='struct scene_case { unsigned int x; unsigned char y; unsigned int width; unsigned char height,flags; };\n'
    header+='static const struct scene_case cases[8] = {'+','.join('{'+','.join(map(str,c))+'}' for c in CASES)+'};\n'
    header+='static const unsigned int expected[8] = {'+','.join(str(n)+'u' for n in refs)+'};\n'
    (WORK / 'expected.h').write_text(header)
    manager=candidate(SOURCE.read_text())
    prefix=manager.split('static void increment_counter(',1)[0]
    start=manager.index('static struct udeks_window *window_by_handle(')
    lookup=manager[start:manager.index('\n}\n',start)+3]
    unit=prefix+'\n'+lookup+'\n'+(ROOT / 'bench/window-repaint-raster/chrome.inc').read_text()
    unit+='\n'+(ROOT / 'bench/window-repaint-raster/raster.inc').read_text()
    unit+='\n#include "probe.inc"\n'
    (WORK / 'native.c').write_text(unit)
    graphics=(ROOT / 'src/services/display/vic_graphics.c').read_text()
    span=graphics.split('/* Private serialized row parameters;',1)[1].split('void udeks_vic_bitmap_fill(',1)[0]
    span='/* Private serialized row parameters;'+span
    display=graphics.split('static void increment_counter(',1)[0]+'\n'+span+'\n'
    display+='\n'.join(function(graphics,n) for n in ('udeks_vic_bitmap_fill','udeks_vic_bitmap_set_clip','udeks_vic_bitmap_reset_clip'))
    (WORK / 'display.c').write_text(display)
    for name in ('native','display'):
        subprocess.run(['cc65','-t','none','--standard','c99','-Oirs','-I',str(ROOT / 'include'),'-I',str(WORK),
            '-I',str(ROOT / 'bench/window-repaint-raster'),
            '-o',str(WORK / (name+'.s')),str(WORK / (name+'.c'))],check=True)
        subprocess.run(['ca65','-o',str(WORK / (name+'.o')),str(WORK / (name+'.s'))],check=True)
    for name,path,include in (('launcher',WORK / 'launcher.s',ROOT / 'bench/window-repaint-bank'),
                             ('driver',WORK / 'driver.s',ROOT / 'bench/window-repaint-bank'),
                             ('pixel',ROOT / 'src/services/display/vic_pixel.s',ROOT / 'src/services/display'),
                             ('span',ROOT / 'src/services/display/vic_span.s',ROOT / 'src/services/display')):
        subprocess.run(['ca65','-I',str(include),'-o',str(WORK / (name+'.o')),str(path)],check=True)
    subprocess.run(['cl65','-t','none','-C',str(ROOT / 'bench/window-repaint-raster/probe.cfg'),
        '-m',str(WORK / 'native.map'),'-o',str(WORK / 'native.bin'),
        *[str(WORK / (n+'.o')) for n in ('launcher','native','display','driver','pixel','span','receipt','binding')]],check=True)
    (WORK / 'native.prg').write_bytes(b'\x00\x20'+(WORK / 'native.bin').read_bytes())
    (WORK / 'expected-final.bin').write_bytes(reference(7))
    return {'scope':'real C/ASM shadow raster and banked receipts; mock row client and memory-only page commit, no live OS/NMI/hardware',
        'scene_checksums':refs,'final_sha256':digest(WORK / 'expected-final.bin'),
        'native_sha256':digest(WORK / 'native.prg'),'segments':segments((WORK / 'native.map').read_text())}


def binding():
    bank = ROOT / 'bench/window-repaint-bank'
    subprocess.run(['ca65','-I',str(bank),'-o',str(WORK / 'gateway.o'),str(bank / 'gateway.s')],check=True)
    subprocess.run(['ld65','-C',str(ROOT / 'bench/window-cache-c-runtime/gateway.cfg'),
                    '-o',str(WORK / 'gateway.bin'),str(WORK / 'gateway.o')],check=True)
    text = (bank / 'binding.s').read_text()
    if text.count('_private_cache_policy_call') != 2:
        raise ValueError('private binding symbol seam changed')
    text = text.replace('_private_cache_policy_call','_private_repaint_policy_call')
    old = 'build/bench/window-repaint-bank/gateway.bin'
    if text.count(old) != 1: raise ValueError('gateway image seam changed')
    text = text.replace(old,str(WORK / 'gateway.bin'))
    (WORK / 'binding.s').write_text(text)
    subprocess.run(['ca65','-I',str(bank),'-o',str(WORK / 'binding.o'),str(WORK / 'binding.s')],check=True)


def whole_links():
    """Keep legacy composition for a closure measurement, not a runnable adapter.

    Granting its old bodies as eventual replacement budget is reported ONLY
    as a component lower bound. Real poll/admission/provider code remains open.
    Every split output is isolated and all derived import bindings are stale.
    """
    links = {}
    for normal in (True,False):
        name = 'normal' if normal else 'panic'
        config = '8502-bootstrap.cfg' if normal else '8502-panic-probe.cfg'
        target = 'build/8502/udeks-8502.bin' if normal else 'build/8502/udeks-8502-panic-probe.bin'
        dry = subprocess.check_output(['make','-Bn',target],cwd=ROOT,text=True)
        command = link_command(dry.replace('cfg/8502-panic-probe.cfg','cfg/8502-bootstrap.cfg'))
        maps = {}; libraries = {}; dirs = {}
        for variant in ('baseline','replacement'):
            directory = WORK / name / variant
            directory.mkdir(parents=True,exist_ok=True); dirs[variant] = directory
            cfg = directory / 'isolated.cfg'
            cfg.write_text(isolated_config((ROOT / 'cfg' / config).read_text(),directory))
            link = list(command)
            link[link.index('-C')+1] = str(cfg)
            link[link.index('-m')+1] = str(directory / 'kernel.map')
            link[link.index('-o')+1] = str(directory / 'kernel.bin')
            if variant == 'replacement':
                link[link.index('build/8502/window_manager.o')] = str(WORK / 'replacement.o')
                link += [str(WORK / 'receipt.o'),str(WORK / 'binding.o')]
            subprocess.run(link,cwd=ROOT,check=True)
            text = (directory / 'kernel.map').read_text()
            maps[variant] = segments(text); libraries[variant] = library_inventory(text)
        if (dirs['baseline'] / 'kernel.bin').read_bytes() != (ROOT / target).read_bytes():
            raise ValueError('isolated baseline bytes differ from normal build')
        if maps['baseline'] != segments((ROOT / target.replace('.bin','.map')).read_text()):
            raise ValueError('isolated baseline map differs from normal build')
        old,new = maps['baseline'],maps['replacement']
        fixed = set(old)-{'CODE','RODATA','DATA','BSS','VICSHADOW'}
        if set(old) != set(new) or any(old[n] != new[n] for n in fixed):
            raise ValueError('sizing link changed a fixed segment or HIGHBSS')
        if any(old[n]['size'] != new[n]['size'] for n in ('RODATA','DATA','BSS','VICSHADOW')):
            raise ValueError('sizing link acquired uncharged data/state')
        old_lib,new_lib = libraries['baseline'],libraries['replacement']
        library_delta = {}
        for modules,sign in ((new_lib,1),(old_lib,-1)):
            for module in modules.values():
                for segment,size in module.items():
                    library_delta[segment] = library_delta.get(segment,0) + sign * size
        if any(size for segment,size in library_delta.items() if segment != 'CODE'):
            raise ValueError('new runtime helpers acquired non-CODE allocation')
        paths = [ROOT / t for t in command if t.endswith('.o')] + [ROOT / target, ROOT / target.replace('.bin','.map')]
        links[name] = {'baseline':old,'replacement':new,'code_growth':new['CODE']['size']-old['CODE']['size'],
            'library_delta':library_delta.get('CODE',0),'library_segment_delta':library_delta,
            'added_helpers':sorted(set(new_lib)-set(old_lib)), 'removed_helpers':sorted(set(old_lib)-set(new_lib)),
            'library_modules':new_lib,'input_sha256':{str(p.relative_to(ROOT)):digest(p) for p in paths},
            'command':command}
    providers = {n.split('(',1)[0] for link in links.values() for n in link['library_modules']}
    if len(providers) != 1: raise ValueError('ambiguous runtime library')
    provider = Path(providers.pop()); provider = provider if provider.is_absolute() else ROOT / provider
    shutil.copy2(provider,WORK / 'none.lib')
    return links


def compact_source(source):
    source = raster_source(candidate(source))
    old = function(source, 'draw_chrome_row')
    # Replace the complete old body, keeping old call sites and the sizing-only
    # synchronous wrapper. New scratch is explicitly charged, not overlaid.
    source = source.replace(old, (ROOT / 'bench/window-repaint-raster/chrome.inc').read_text())
    old_backend = (ROOT / 'bench/window-repaint-lane/raster.inc').read_text()
    if source.count(old_backend) != 1:
        raise ValueError('raster seam changed')
    return source.replace(old_backend,
        (ROOT / 'bench/window-repaint-raster/raster.inc').read_text())


def verify_components(objects):
    replacement=objects['replacement']
    required={'_chrome_pixel','_chrome_span','_draw_chrome_row','_lane_raster_step','_draw_chrome'}
    if not required <= set(replacement['functions']):raise ValueError('compiler omitted a charged renderer entry')
    if objects['compact']['segments']['HIGHBSS']!=76 or replacement['segments']['HIGHBSS']!=88:
        raise ValueError('explicit scratch/state allocation changed')
    for n in ('replacement','receipt','binding'):
        if any(objects[n]['segments'].get(s,0) for s in ('BSS','DATA','ZEROPAGE')):
            raise ValueError('uncharged mutable allocation')
    if objects['receipt']['segments'].get('HIGHBSS',0) or objects['binding']['segments'].get('HIGHBSS',0):
        raise ValueError('receipt/binding acquired persistent scratch')


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    results = {}
    sources = {'compact': candidate(SOURCE.read_text()),
               'previous': raster_source(candidate(SOURCE.read_text())),
               'replacement': compact_source(SOURCE.read_text())}
    for name, text in sources.items():
        stem = WORK / name
        stem.with_suffix('.c').write_text(text)
        subprocess.run(['cc65','-t','none','--cpu','6502','--standard','c99','-Oirs',
            '-I',str(ROOT / 'include'),'-o',str(stem.with_suffix('.s')),str(stem.with_suffix('.c'))],check=True)
        subprocess.run(['ca65','-l',str(stem.with_suffix('.lst')),'-o',str(stem.with_suffix('.o')),
            str(stem.with_suffix('.s'))],check=True)
        results[name] = {'segments':object_sizes(stem.with_suffix('.o')),
                        'functions':listing_functions(stem.with_suffix('.lst').read_text()),
                        'imports':imports(stem.with_suffix('.o'))}
    stem = WORK / 'receipt'
    subprocess.run(['cc65','-t','none','--cpu','6502','--standard','c99','-Oirs',
        '-I',str(ROOT / 'include'),'-o',str(stem.with_suffix('.s')),
        str(ROOT / 'bench/window-repaint-raster/receipt.c')],check=True)
    subprocess.run(['ca65','-l',str(stem.with_suffix('.lst')),'-o',str(stem.with_suffix('.o')),
        str(stem.with_suffix('.s'))],check=True)
    results['receipt'] = {'segments':object_sizes(stem.with_suffix('.o')),
        'functions':listing_functions(stem.with_suffix('.lst').read_text()),'imports':imports(stem.with_suffix('.o'))}
    binding()
    results['binding'] = {'segments':object_sizes(WORK / 'binding.o')}
    report = {'scope':'UNBOOTABLE isolated closure sizing; legacy composition retained, no poll/provider/delivery integration',
              'objects':results,'links':whole_links()}
    verify_components(results)
    old=sum(results['compact']['functions'][n]['size'] for n in
        ('_draw_glyph','_draw_title','_draw_chrome','_paint_window_damage','_compose_damage'))
    row=sum(results['replacement']['functions'][n]['size'] for n in ('_chrome_pixel','_chrome_span','_draw_chrome_row'))
    backend=results['replacement']['functions']['_lane_raster_step']['size']
    closure={r['library_delta'] for r in report['links'].values()}
    if len(closure)!=1:raise ValueError('normal/panic helper closure differs')
    report['component_budget']={'row_with_helpers':row,'backend':backend,'receipt':results['receipt']['segments']['CODE'],
        'binding':results['binding']['segments']['CODE'],'new_helper_closure':closure.pop(),'old_bodies':old,'reserve':137}
    b=report['component_budget'];b['charged']=sum(b[n] for n in ('row_with_helpers','backend','receipt','binding','new_helper_closure'))
    b['optimistic_headroom']=b['old_bodies']+b['reserve']-b['charged']
    b['scope']='lower bound grants retired bodies/reserve, excludes real poll/view/admission/provider/busy/teardown costs'
    report['native']=native_build()
    if report['native']['segments']['HIGHBSS']['size']!=88 or report['native']['segments']['VICSHADOW']['start']!=0xA1E0:
        raise ValueError('native renderer state or unaligned shadow moved')
    paths=[SOURCE,Path(__file__),ROOT / 'src/services/display/vic_graphics.c',
        ROOT / 'src/services/display/vic_pixel.s',ROOT / 'src/services/display/vic_span.s',
        ROOT / 'tools/window_repaint_bank.py',ROOT / 'tools/window_repaint_compact.py',
        ROOT / 'tools/repaint_lane_budget.py',ROOT / 'tools/graphics_raster_link_audit.py',
        ROOT / 'tools/graphics_raster_bench_build.py',ROOT / 'tools/graphics_cache_placement.py',
        ROOT / 'tools/graphics_span_bench.py',ROOT / 'tools/placement_audit.py',
        ROOT / 'tools/gen_capability_imports.py',ROOT / 'tools/window_cache_manager.py',
        ROOT / 'tools/1986_raster_bench.c',ROOT / 'tools/1986_input_smoke_build.py',
        ROOT / 'tools/graphics_raster_bench_run.py',ROOT / 'tools/vice_capture.py',
        ROOT / 'cfg/8502-bootstrap.cfg',ROOT / 'cfg/8502-panic-probe.cfg',
        ROOT / 'Makefile',ROOT / 'mk/toolchain.mk',ROOT / 'tests/test_window_repaint_raster_compact.py',
        ROOT / 'tests/test_window_repaint_raster_budget.py',
        ROOT / 'tests/test_repaint_raster.py',ROOT / 'tests/test_repaint_chrome_rows.py',
        ROOT / 'tests/test_window_cache_manager.py',ROOT / 'tests/test_window_cache_partial_manager.py',
        ROOT / 'bench/window-cache-manager/occlusion-host.inc']
    paths+=list((ROOT / 'bench/window-repaint-raster').iterdir())
    paths += [ROOT / 'bench' / directory / name for directory,names in (
        ('window-repaint-lane',('chrome.inc','raster.inc')),
        ('window-repaint-bank',('binding.s','gateway.s','layout.inc','packet.h')),
        ('window-cache-c-runtime',('driver.s','gateway.cfg'))) for name in names]
    paths += [ROOT / 'include/udeks' / n for n in ('window.h','vic_graphics.h','memory.h','pointer.h',
        'window_cache_state.h','window_cache_command.h','window_repaint.h','repaint_lane.h')]
    paths += [ROOT / 'bench/artifacts/2026-09-29-repaint-bank' / n for n in ('SHA256SUMS',
        'build/module-envelope.bin','build/launcher.s','build/build-report.json','build/none.lib')]
    inputs={str(p.relative_to(ROOT)):digest(p) for p in paths}
    for link in report['links'].values():inputs.update(link['input_sha256'])
    report['input_sha256']=inputs
    # Keep all split linker outputs, provider objects and generated C/ASM.
    report['output_sha256']={str(p.relative_to(WORK)):digest(p) for p in sorted(WORK.rglob('*'))
        if p.is_file() and p.name not in ('budget.json','1986-raster','runner.c')}
    report['toolchain']={n:subprocess.check_output([n,'--version'],stderr=subprocess.STDOUT,text=True).strip()
        for n in ('cc65','ca65','ld65','cl65')}
    (WORK / 'budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({n:{'segments':r['segments'],'measured':{k:v['size'] for k,v in r.get('functions',{}).items()
        if k in ('_draw_chrome_row','_lane_raster_step','_draw_chrome')}} for n,r in results.items()},indent=2))
    print(json.dumps({n:{k:r[k] for k in ('code_growth','library_delta','added_helpers','removed_helpers')}
        for n,r in report['links'].items()},indent=2))
    print(json.dumps(report['component_budget'],indent=2))


def decode(data):
    if len(data)!=8096 or data[:9]!=b'RAST\x01\x02\x00\x00\x08':raise ValueError('incomplete/failed raster record')
    if any(data[9:12]) or any(data[16:23]) or data[24]!=15 or any(data[25:32]) or any(data[48:64]) or any(data[8064:]):
        raise ValueError('raster runtime/guard/reserved failure')
    if not 0x40<=data[23]<0xF0:raise ValueError('private stack/guard coverage failure')
    irq=int.from_bytes(data[12:16],'little')
    if not irq:raise ValueError('no IRQ arrivals')
    refs=[checksum(reference(i)) for i in range(8)]
    got=[int.from_bytes(data[32+i*2:34+i*2],'little') for i in range(8)]
    if got!=refs or data[64:8064]!=reference(7):raise ValueError('native pixels diverged from old-window oracle')
    return {'scenes':8,'scene_checksums':got,'interrupts':irq,'lowest_changed_stack_offset':data[23],
            'final_sha256':hashlib.sha256(data[64:8064]).hexdigest()}


def run(engine,output,emulator):
    from graphics_raster_bench_run import emulator_provenance
    report=json.loads((WORK / 'budget.json').read_text())
    verify(report)
    output.mkdir(parents=True,exist_ok=True)
    if engine=='1986':
        sources=importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
        provenance=emulator_provenance(emulator,sources)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
        runner=WORK / '1986-raster'
        runner_text=(ROOT / 'tools/1986_raster_bench.c').read_text()
        if runner_text.count('frames < 4000')!=1:raise ValueError('runner frame budget seam changed')
        # Real raster + full-image oracle scans are deliberately heavy. This
        # is a termination budget, NEVER an input-latency acceptance bound.
        (WORK / 'runner.c').write_text(runner_text.replace('frames < 4000','frames < 16000'))
        subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator / 'src'),
            str(WORK / 'runner.c'),*map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
        command=[str(runner),str(WORK / 'native.prg'),str(output / '1986.bin'),'RAST']
    else:
        provenance=subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True)
        command=['python3',str(ROOT / 'tools/vice_capture.py'),str(WORK / 'native.prg'),str(output / 'vice.bin'),
            '--entry','0x2000','--raw-load','--result-address','0x7fc0','--result-size','8096','--state-offset','5','--timeout','90']
    subprocess.run(command,check=True)
    data=(output / (engine+'.bin')).read_bytes();result=decode(data)
    verify(report)
    if engine=='1986' and emulator_provenance(emulator,sources)!=provenance:raise ValueError('emulator drift')
    (output / (engine+'.json')).write_text(json.dumps({'decoded':result,'raw_sha256':hashlib.sha256(data).hexdigest(),
        'native_sha256':report['native']['native_sha256'],'build_report_sha256':digest(WORK / 'budget.json'),
        'provenance':provenance},indent=2)+'\n')
    print(json.dumps(result,indent=2))


def verify(report):
    for n,sha in report['input_sha256'].items():
        if digest(ROOT / n)!=sha:raise ValueError('input drift '+n)
    for n,sha in report['output_sha256'].items():
        if digest(WORK / n)!=sha:raise ValueError('build drift '+n)


def preserve(output):
    report=json.loads((WORK / 'budget.json').read_text());verify(report)
    for engine in ('1986','vice'):
        run=json.loads((output / (engine+'.json')).read_text())
        if run['native_sha256']!=report['native']['native_sha256']:raise ValueError('run/program mismatch')
        if run['build_report_sha256']!=digest(WORK / 'budget.json'):raise ValueError('run/report mismatch')
        data=(output / (engine+'.bin')).read_bytes()
        if hashlib.sha256(data).hexdigest()!=run['raw_sha256'] or decode(data)!=run['decoded']:
            raise ValueError('raw/decode drift')
    art=ROOT / 'bench/artifacts' / NAME; result=ROOT / 'bench/results' / NAME
    if art.exists() or result.exists():raise ValueError('refusing to overwrite evidence')
    art.mkdir(parents=True);result.mkdir(parents=True)
    for prefix,files,base in (('inputs',report['input_sha256'],ROOT),('build',report['output_sha256'],WORK)):
        for n in files:
            dest=art / prefix / n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(base / n,dest)
    shutil.copy2(WORK / 'budget.json',result / 'budget.json')
    for engine in ('1986','vice'):
        for suffix in ('.bin','.json'):shutil.copy2(output / (engine+suffix),result / (engine+suffix))
    for directory in (art,result):
        files=sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in files))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',nargs='?',default='build',choices=('build','run','preserve'))
    p.add_argument('--engine',choices=('1986','vice'));p.add_argument('--emulator-root',type=Path,default=Path('/var/home/salvogendut/Dev/1986'))
    p.add_argument('--output',type=Path,default=ROOT / 'build/window-repaint-raster-results');a=p.parse_args()
    if a.action=='build':build()
    elif a.action=='preserve':preserve(a.output)
    else:
        if not a.engine:p.error('run requires --engine')
        run(a.engine,a.output,a.emulator_root)

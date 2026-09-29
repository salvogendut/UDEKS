#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private value-prefix relocation / full-link sizing, never an OS disk."""
import json
from pathlib import Path
import shutil
import subprocess
import argparse
from graphics_cache_placement import listing_functions
from graphics_span_bench import object_sizes
from placement_audit import parse_map
from window_repaint_compact import imports
import window_repaint_raster as raster
import window_repaint_bank as bank
BASE_DECODE = raster.decode

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT / 'build/window-repaint-scenes'
SOURCE=ROOT / 'bench/window-repaint-scenes'
NAME='2026-09-29-repaint-scenes'
PRIOR=ROOT / 'bench/results/2026-09-29-repaint-frontend/budget.json'
LAYOUT=bytes([0,1,3,4,6,7,8,8,82,10,52,3,64])

def digest(path):return raster.digest(path)

def frontend(text):
    signature='unsigned char repaint_frontend_poll('
    start=text.index(signature)
    if text.count(signature)!=1 or not text.endswith('}\n'):
        raise ValueError('private poll seam changed')
    text=text[:start]+(SOURCE / 'poll.inc').read_text()
    header='#include "../window-repaint-bank/packet.h"'
    if text.count(header)!=1:raise ValueError('private header seam changed')
    return text.replace(header,'#include "../window-repaint-scenes/packet.h"')

def compile_c(name,text):
    stem=WORK / name;stem.with_suffix('.c').write_text(text)
    subprocess.run(['cc65','-t','none','--cpu','6502','--standard','c99','-Oirs',
        '-I',str(ROOT / 'include'),'-I',str(WORK),'-I',str(SOURCE),'-o',str(stem.with_suffix('.s')),str(stem.with_suffix('.c'))],check=True)
    subprocess.run(['ca65','-l',str(stem.with_suffix('.lst')),'-o',str(stem.with_suffix('.o')),str(stem.with_suffix('.s'))],check=True)
    return {'segments':object_sizes(stem.with_suffix('.o')),
        'functions':{} if name.startswith('layout') else listing_functions(stem.with_suffix('.lst').read_text()),'imports':imports(stem.with_suffix('.o'))}

def layout(source,label='layout',header=None,check=True):
    start=source.index('struct udeks_window {')
    end=source.index('\n};',start)+3
    text=('#include "packet.h"\n' if header is None else header+'\n')+source[start:end]+'\nconst unsigned char layout[] = {'
    text+=','.join('offsetof(struct udeks_window,'+n+')' for n in ('flags','x','y','width','height','z','title'))
    text+=',sizeof(struct repaint_scene),sizeof(struct repaint_packet),'+','.join(
        'offsetof(struct repaint_packet,'+n+')' for n in ('ticket','work','result','snapshot'))+'};\n'
    text='#include "udeks/window.h"\n'+text
    obj=compile_c(label,text)
    if obj['segments']['CODE'] or obj['segments']['RODATA']!=13:raise ValueError('layout sidecar acquired executable code')
    subprocess.run(['ld65','-C',str(SOURCE / 'layout.cfg'),'-o',str(WORK / (label+'.bin')),str(WORK / (label+'.o'))],check=True)
    data=(WORK / (label+'.bin')).read_bytes()
    if check and data!=LAYOUT:raise ValueError('target prefix/wire layout changed')
    return data

def native_build():
    # Reuse the audited real-raster diagnostic, then replace its policy/driver
    # envelope and exercise THIS frontend, not a handwritten packing substitute.
    module=(WORK / 'module-envelope.bin').read_bytes()
    shutil.copy2(ROOT / 'bench/window-repaint-raster/probe.inc',WORK / 'probe.inc')
    old=raster.WORK
    try:raster.WORK=WORK;raster.native_build()
    finally:raster.WORK=old
    (WORK / 'module-envelope.bin').write_bytes(module)
    text=(WORK / 'native.c').read_text()
    text=text.replace('#include "probe.inc"','')
    text+='\n#include "udeks/window_cache_state.h"\nvolatile unsigned char cache_accept_state=0x80,cache_phase;\n'
    text+='unsigned char udeks_vic_graphics_is_active(void) { return 1; }\n'
    text+=frontend((ROOT / 'bench/window-repaint-frontend/frontend.inc').read_text())+'\n#include "probe.inc"\n'
    probe=(ROOT / 'bench/window-repaint-raster/probe.inc').read_text().replace('#include "../window-repaint-bank/packet.h"','')
    probe=bank.replace_once(probe,'V(RECORD+4)=1;V(RECORD+5)=1;','V(RECORD+4)=2;V(RECORD+5)=1;')
    start=probe.index('        packet.count=1;');end=probe.index('        packet.damage.left=',start)
    probe=probe[:start]+probe[end:]
    probe=bank.replace_once(probe,'w->flags=cases[current_case].flags;w->z=1;',
        'w->flags=cases[current_case].flags|UDEKS_WINDOW_FLAG_VISIBLE;w->z=1;')
    probe=bank.replace_once(probe,'result=request(REPAINT_PEEK);','result=repaint_frontend_poll(1,&work);')
    probe=bank.replace_once(probe,'if(result!=UDEKS_REPAINT_OK){check(0,2);break;}\n        work=packet.work; /* LOCAL copy: pixels/IPC can overwrite common RAM. */\n        result=lane_raster_step(&work);',
        'if(result!=UDEKS_REPAINT_OK && result!=UDEKS_LANE_BACKEND_REQUIRED){check(0,2);break;}')
    # cancel_on_glyph also peeks: have the real frontend publish values, then
    # issue a second PEEK to capture the unexecuted row that must go stale.
    probe=bank.replace_once(probe,'check(request(REPAINT_PEEK)==0,11);old=packet.work;',
        'check(repaint_frontend_poll(1,&old)==0,11);check(request(REPAINT_PEEK)==0,11);old=packet.work;')
    probe=bank.replace_once(probe,'        check(lane_raster_step(&old)==0,12);','        /* frontend already executed exactly one step; next PEEK is unacknowledged. */')
    proof='''
static void protocol_probe(void)
{
    struct udeks_repaint_lane before;
    unsigned int pixels;
    unsigned char n;
    check(request(REPAINT_INIT)==0,24);
    packet.damage.left=0;packet.damage.right=320;packet.damage.top=0;packet.damage.bottom=200;
    check(request(REPAINT_REQUEST)==0,24);before=packet.snapshot;
    memset(udeks_vic_bitmap_shadow,0x69,8000);memset((void *)0xE190u,0,32);
    udeks_vic_bitmap_set_clip(111,77,2,3);pixels=checksum();
    for(n=0;n<4u;++n) {
        memset(packet.scenes,0,sizeof(packet.scenes));memset(packet.reserved,0,4);
        packet.count=REPAINT_SCENE_FORMAT;
        packet.scenes[0].rank=1;packet.scenes[0].flags=UDEKS_WINDOW_FLAG_VISIBLE;
        packet.scenes[0].width=48;packet.scenes[0].height=48;
        if(n==0)packet.count=4;
        else if(n==1)packet.reserved[3]=1;
        else if(n==2)packet.scenes[0].x=65535u;
        else packet.scenes[0].rank=5;
        check(request(REPAINT_PEEK)==UDEKS_REPAINT_INVALID,25);
        check(memcmp(&before,&packet.snapshot,sizeof(before))==0 && checksum()==pixels,26);
        check(*(unsigned int *)0xE1B0u==111 && *(unsigned int *)0xE1B2u==77 &&
            *(unsigned int *)0xE1B4u==113 && *(unsigned int *)0xE1B6u==80,26);
    }
    V(RECORD+9)=n;
}
'''
    probe=bank.replace_once(probe,'int main(void)',proof+'\nint main(void)')
    probe=bank.replace_once(probe,'    runtime_irq_start();','    runtime_irq_start();protocol_probe();')
    (WORK / 'probe.inc').write_text(probe)
    layout(text,'layout-native')
    compile_c('native',text)
    subprocess.run(['ca65','-I',str(ROOT / 'bench/window-repaint-bank'),'-o',str(WORK / 'driver.o'),str(WORK / 'driver.s')],check=True)
    subprocess.run(['cl65','-t','none','-C',str(ROOT / 'bench/window-repaint-raster/probe.cfg'),
        '-m',str(WORK / 'native.map'),'-o',str(WORK / 'native.bin'),
        *[str(WORK / (n+'.o')) for n in ('launcher','native','display','driver','pixel','span','receipt','binding')]],check=True)
    (WORK / 'native.prg').write_bytes(b'\x00\x20'+(WORK / 'native.bin').read_bytes())

def decode(data):
    if len(data)!=8096 or data[:5]!=b'RAST\x02' or data[9]!=4:
        raise ValueError('wrong/incomplete scene-prefix protocol proof')
    normalized=bytearray(data);normalized[4]=1;normalized[9]=0
    result=BASE_DECODE(normalized);result['protocol_rejections']=4
    return result

def verify_budget(report):
    obj=report['object']
    required=('_chrome_pixel','_chrome_span','_draw_chrome_row','_lane_raster_step',
        '_repaint_frontend_allowed','_repaint_frontend_control','_repaint_frontend_poll')
    if not set(required)<=set(obj['functions']) or set(report['links'])!={'normal','panic'}:
        raise ValueError('incomplete functions/link closure')
    if obj['segments']['HIGHBSS']!=88 or any(obj['segments'].get(n,0) for n in ('BSS','DATA','ZEROPAGE')):
        raise ValueError('new resident persistent state')
    for link in report['links'].values():
        if link['code_growth']!=obj['segments']['CODE']-7762+127+84+link['library_delta']:
            raise ValueError('resident closure charge differs')
    if len({link['library_delta'] for link in report['links'].values()})!=1:raise ValueError('panic helper closure differs')
    b=report['budget'];functions=obj['functions']
    measured=sum(functions[n]['size'] for n in required)
    charged=measured+127+84+report['links']['normal']['library_delta']
    if b['charged']!=charged or b['shortfall']!=charged-2113 or b['poll_saving']!=440-functions['_repaint_frontend_poll']['size']:
        raise ValueError('component accounting mismatch')
    bank.verify_layout([(n,*r) for n,r in report['module']['segments'].items()],report['module']['bytes'])
    if report['module']['bytes']!=3+report['module']['objects']['lane']['segments']['CODE']+report['module']['objects']['dispatch']['segments']['CODE']+report['module']['helper_bytes']:
        raise ValueError('bank closure not fully charged')
    if report['module']['code_spare']!=0xEE0-report['module']['bytes']:raise ValueError('bank spare differs')
    if report['module']['local_view_bytes']!=36:raise ValueError('private software-stack views not charged')
    if bytes(report['layout']['expected'])!=LAYOUT or any(bytes(report['layout'][n])==LAYOUT for n in ('negative_prefix','negative_packet')):
        raise ValueError('layout qualification missing/false pass')

def build():
    WORK.mkdir(parents=True,exist_ok=True)
    for directory in (PRIOR.parent,ROOT / 'bench/artifacts/2026-09-29-repaint-frontend'):
        for line in (directory / 'SHA256SUMS').read_text().splitlines():
            sha,name=line.split('  ',1)
            if digest(directory / name)!=sha:raise ValueError('prior frontend evidence changed')
    bank.verify_ownership((ROOT / 'include/udeks/memory.h').read_text(),(ROOT / 'src/services/window/cache/layout.inc').read_text())
    text=raster.compact_source(raster.SOURCE.read_text())+'\n'+frontend((ROOT / 'bench/window-repaint-frontend/frontend.inc').read_text())
    layout(text,'layout-resident')
    negative_prefix=layout(text.replace('    unsigned char flags;','    unsigned char poison;\n    unsigned char flags;',1),'layout-bad-prefix',check=False)
    negative_packet=layout(text,'layout-bad-packet',header=(SOURCE / 'packet.h').read_text().replace('    uint8_t flags;','    uint8_t poison, flags;',1),check=False)
    if negative_prefix==LAYOUT or negative_packet==LAYOUT:raise ValueError('layout negative controls falsely pass')
    obj=compile_c('replacement',text)
    proof=ROOT / 'bench/artifacts/2026-09-29-repaint-raster/build'
    for n in ('receipt.o','binding.o'):shutil.copy2(proof / n,WORK / n)
    old=raster.WORK
    try:raster.WORK=WORK;links=raster.whole_links()
    finally:raster.WORK=old
    dispatch=compile_c('dispatch',(SOURCE / 'dispatch.c').read_text())
    lane=compile_c('lane',(ROOT / 'src/services/window/repaint_lane.c').read_text())
    subprocess.run(['ca65','-o',str(WORK / 'module.o'),str(ROOT / 'bench/window-repaint-bank/module.s')],check=True)
    subprocess.run(['cl65','-t','none','-C',str(ROOT / 'bench/window-repaint-bank/module.cfg'),
        '-m',str(WORK / 'module.map'),'-o',str(WORK / 'module.bin'),
        *[str(WORK / (n+'.o')) for n in ('module','dispatch','lane')]],check=True)
    modules,segs=parse_map((WORK / 'module.map').read_text());module=(WORK / 'module.bin').read_bytes()
    bank.verify_layout(segs,len(module))
    if any(dispatch['segments'].get(n,0) for n in ('BSS','DATA','ZEROPAGE','HIGHBSS','RODATA')):
        raise ValueError('decoder allocated persistent state/data')
    (WORK / 'module-envelope.bin').write_bytes(module.ljust(0xF00,b'\0'))
    native_build()
    library_paths={n.split('(',1)[0] for n in modules if 'none.lib(' in n}
    if len(library_paths)!=1:raise ValueError('missing module helper provider')
    provider=Path(library_paths.pop())
    shutil.copy2(provider,WORK / 'bank-none.lib')
    helpers={n:s for n,s in modules.items() if 'none.lib(' in n}
    for name,s in helpers.items():
        expected_zp=26 if name.endswith('(zeropage.o)') else 0
        if s.get('ZEROPAGE',0)!=expected_zp or any(size for n,size in s.items() if n not in ('CODE','ZEROPAGE')):
            raise ValueError('bank runtime allocated non-code state beyond published ZP')
    helper_bytes=sum(s.get('CODE',0) for s in helpers.values())
    measured=sum(obj['functions'][n]['size'] for n in ('_chrome_pixel','_chrome_span','_draw_chrome_row','_lane_raster_step',
        '_repaint_frontend_allowed','_repaint_frontend_control','_repaint_frontend_poll'))
    charged=measured+127+84+links['normal']['library_delta']
    report={'scope':'UNBOOTABLE isolated sizing and standalone scene-prefix runtime; not production poll/lifecycle/admission/NMI/provider delivery',
        'object':obj,'links':links,'budget':{'charged':charged,'shortfall':charged-2113,'poll_saving':440-obj['functions']['_repaint_frontend_poll']['size'],
            'scope':'lower bound; legacy damage/cache helpers NOT retired, call-site/admission/delivery/NMI/providers/teardown excluded'},
        'module':{'bytes':len(module),'segments':{n:[s,e] for n,s,e in segs},'code_spare':0xEE0-len(module),
            'objects':{'lane':lane,'dispatch':dispatch},'helper_bytes':helper_bytes,'helpers':helpers,'local_view_bytes':36},
        'layout':{'expected':list(LAYOUT),'negative_prefix':list(negative_prefix),'negative_packet':list(negative_packet)},
        'native':{'native_sha256':digest(WORK / 'native.prg'),'segments':raster.segments((WORK / 'native.map').read_text()),
            'scope':'actual prefix frontend and banked C view decoder plus real C/ASM raster; mock client/commit/admission, no live OS/apps/NMI/HW/latency qualification',
            'scene_checksums':[raster.checksum(raster.reference(i)) for i in range(8)],'protocol_rejections':4,'final_sha256':digest(WORK / 'expected-final.bin')},
        'toolchain':{n:subprocess.check_output([n,'--version'],stderr=subprocess.STDOUT,text=True).strip() for n in ('cc65','ca65','ld65','cl65')}}
    verify_budget(report)
    if report['native']['segments']['HIGHBSS']['size']!=88:raise ValueError('native manager state grew')
    inputs=[Path(__file__),PRIOR,PRIOR.parent / 'SHA256SUMS',ROOT / 'bench/artifacts/2026-09-29-repaint-frontend/SHA256SUMS',
        ROOT / 'bench/window-repaint-frontend/frontend.inc',ROOT / 'src/services/window/window_manager_cached.c',
        ROOT / 'src/services/window/repaint_lane.c',ROOT / 'src/services/display/vic_graphics.c',ROOT / 'src/services/display/vic_pixel.s',ROOT / 'src/services/display/vic_span.s',
        ROOT / 'Makefile',ROOT / 'mk/toolchain.mk',ROOT / 'cfg/8502-bootstrap.cfg',ROOT / 'cfg/8502-panic-probe.cfg',
        ROOT / 'tests/test_window_repaint_scenes.py',ROOT / 'tests/test_window_repaint_scenes_budget.py',ROOT / 'tests/test_window_repaint_frontend.py',
        ROOT / 'tests/test_window_cache_manager.py',ROOT / 'tests/test_window_cache_partial_manager.py',ROOT / 'bench/window-cache-manager/occlusion-host.inc']
    inputs+=list(SOURCE.iterdir())+list((ROOT / 'include/udeks').glob('*.h'))
    inputs += [ROOT / 'tools' / n for n in ('window_repaint_raster.py','window_repaint_bank.py','window_repaint_compact.py','repaint_lane_budget.py',
        'graphics_cache_placement.py','graphics_span_bench.py','graphics_raster_bench_build.py','graphics_raster_link_audit.py','placement_audit.py',
        'gen_capability_imports.py','window_cache_manager.py','1986_raster_bench.c','1986_input_smoke_build.py','graphics_raster_bench_run.py','vice_capture.py')]
    for directory,names in (('window-repaint-raster',('chrome.inc','raster.inc','receipt.c','probe.inc','probe.cfg')),
            ('window-repaint-lane',('chrome.inc','raster.inc')),('window-repaint-bank',('module.s','module.cfg','gateway.s','binding.s','layout.inc','packet.h')),
            ('window-cache-c-runtime',('driver.s','gateway.cfg')),('artifacts/2026-09-29-repaint-bank',('SHA256SUMS','build/module-envelope.bin','build/launcher.s')),
            ('artifacts/2026-09-29-repaint-raster',('SHA256SUMS','build/receipt.o','build/binding.o'))):
        inputs += [ROOT / 'bench' / directory / n for n in names]
    report['input_sha256']={str(p.relative_to(ROOT)):digest(p) for p in inputs}
    for link in links.values():report['input_sha256'].update(link['input_sha256'])
    report['output_sha256']={str(p.relative_to(WORK)):digest(p) for p in sorted(WORK.rglob('*'))
        if p.is_file() and p.name not in ('budget.json','1986-raster','runner.c')}
    (WORK / 'budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({n:report[n] for n in ('scope','budget','layout')},indent=2))

def run(engine,output,emulator):
    old_work,old_decode=raster.WORK,raster.decode
    try:
        raster.WORK=WORK;raster.decode=decode
        raster.run(engine,output,emulator)
    finally:raster.WORK=old_work;raster.decode=old_decode

def preserve(output):
    old_work=raster.WORK
    try:raster.WORK=WORK;raster.verify(json.loads((WORK / 'budget.json').read_text()))
    finally:raster.WORK=old_work
    report=json.loads((WORK / 'budget.json').read_text());verify_budget(report)
    for engine in ('1986','vice'):
        r=json.loads((output / (engine+'.json')).read_text());data=(output / (engine+'.bin')).read_bytes()
        if r['native_sha256']!=report['native']['native_sha256'] or r['build_report_sha256']!=digest(WORK / 'budget.json'):
            raise ValueError('run/report/program mismatch')
        if digest(output / (engine+'.bin'))!=r['raw_sha256'] or decode(data)!=r['decoded']:raise ValueError('result drift')
    art=ROOT / 'bench/artifacts' / NAME;result=ROOT / 'bench/results' / NAME
    if art.exists() or result.exists():raise ValueError('refusing to overwrite evidence')
    for prefix,files,base in (('inputs',report['input_sha256'],ROOT),('build',report['output_sha256'],WORK)):
        for n in files:
            p=art / prefix / n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(base / n,p)
    result.mkdir(parents=True);shutil.copy2(WORK / 'budget.json',result / 'budget.json')
    for engine in ('1986','vice'):
        for suffix in ('.bin','.json'):shutil.copy2(output / (engine+suffix),result / (engine+suffix))
    for directory in (art,result):
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in sorted(directory.rglob('*')) if p.is_file()))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',nargs='?',default='build',choices=('build','decode','run','preserve'))
    parser.add_argument('record',nargs='?',type=Path);parser.add_argument('--engine',choices=('1986','vice'))
    parser.add_argument('--output',type=Path,default=ROOT / 'build/window-repaint-scenes-results')
    parser.add_argument('--emulator-root',type=Path,default=Path('/var/home/salvogendut/Dev/1986'));args=parser.parse_args()
    if args.action=='build':build()
    elif args.action=='decode':print(json.dumps(decode(args.record.read_bytes()),indent=2))
    elif args.action=='run':
        if not args.engine:parser.error('run requires --engine')
        run(args.engine,args.output,args.emulator_root)
    else:preserve(args.output)

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the bounded C command + row copier under one private runtime lease."""
import argparse
import hashlib
import importlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT / 'build/bench/window-cache-command'
NAME='2026-09-28-window-cache-command'
OLD=ROOT / 'bench/window-cache-c-runtime'
SOURCE=ROOT / 'bench/window-cache-command'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    from graphics_span_bench import object_sizes
    from placement_audit import parse_map
    WORK.mkdir(parents=True,exist_ok=True)
    # Reuse the qualified diagnostic guard scanner, never its resident binding.
    driver=(OLD / 'driver.s').read_text()
    driver=driver.replace(', _vic_cache_row_candidate','')
    start=driver.index('_runtime_row:\n');end=driver.index('_runtime_check_memory:\n')
    driver=driver[:start]+driver[end:]
    driver=driver.replace(', _runtime_row','')
    driver=driver.replace('#$0b                ; exact private $4200-$4CFF envelope',
                          '#$0d                ; exact private $4200-$4EFF envelope')
    driver=driver.replace('#$13\n', '#$09\n') # ten bytes after 22-byte state
    driver=driver.replace('$f740','$ff80')    # combined gateway owns through $F76E
    driver=driver.replace('$ff80+irq_end-irq <= $f780', '$ff80+irq_end-irq < $fffa')
    driver=driver.replace('module_image_end-module_image = $b00',
                          'module_image_end-module_image = $d00')
    driver=driver.replace('build/bench/window-cache-c-runtime/module-envelope.bin',
                          'build/bench/window-cache-command/module-envelope.bin')
    (WORK / 'driver.s').write_text(driver)
    launcher=(ROOT / 'bench/graphics-raster/launcher.s').read_text()
    launcher=launcher.replace('#<$7800','#<$eff0').replace('#>$7800','#>$eff0')
    (WORK / 'launcher.s').write_text(launcher)
    sources={'core':ROOT / 'bench/window-cache-overlay/core.s',
             'module':SOURCE / 'module.s','gateway':SOURCE / 'gateway.s'}
    for name,path in sources.items():
        subprocess.run(['ca65','-I',str(SOURCE),'-o',str(WORK / (name+'.o')),str(path)],check=True)
    subprocess.run(['ld65','-C',str(OLD / 'gateway.cfg'),'-o',str(WORK / 'gateway.bin'),
                    str(WORK / 'gateway.o')],check=True)
    for name,path in (('policy',ROOT / 'src/services/window/move_cache_state.c'),
                      ('command',ROOT / 'src/services/window/cache_overlay.c')):
        subprocess.run(['cl65','-t','none','--cpu','6502','-Oirs','--standard','c99',
            '-I',str(ROOT / 'include'),'-c','-o',str(WORK / (name+'.o')),str(path)],check=True)
    subprocess.run(['cl65','-t','none','-C',str(SOURCE / 'module.cfg'),
        '-m',str(WORK / 'module.map'),'-o',str(WORK / 'module.bin'),
        *[str(WORK / (n+'.o')) for n in ('core','module','policy','command')]],check=True)
    module=(WORK / 'module.bin').read_bytes()
    if len(module)>0xce0:raise ValueError('module reaches state')
    (WORK / 'module-envelope.bin').write_bytes(module.ljust(0xd00,b'\x00'))
    for name,path in (('binding',SOURCE / 'binding.s'),('driver',WORK / 'driver.s'),
                      ('launcher',WORK / 'launcher.s')):
        subprocess.run(['ca65','-I',str(SOURCE),'-o',str(WORK / (name+'.o')),str(path)],check=True)
    for case in (0,1):
        stem=WORK / f'probe-{case}'
        subprocess.run(['cl65','-t','none','--standard','c99','-Oirs','-D',f'CASE={case}',
            '-c','-o',str(stem.with_suffix('.o')),str(SOURCE / 'probe.c')],check=True)
        subprocess.run(['cl65','-t','none','-C',str(OLD / 'probe.cfg'),
            '-m',str(stem.with_suffix('.map')),'-o',str(stem.with_suffix('.bin')),
            *[str(WORK / (n+'.o')) for n in ('launcher',f'probe-{case}','driver','binding')]],check=True)
        stem.with_suffix('.prg').write_bytes(b'\x00\x20'+stem.with_suffix('.bin').read_bytes())
    normal=(WORK / 'probe-0.prg').read_bytes();gate=(WORK / 'gateway.bin').read_bytes()
    if normal.count(gate)!=1:raise ValueError('ambiguous live gateway')
    controls={}
    for name,pattern,delta,new in (('irq-leak',b'\x08\x78\xd8',1,0xea),
                                 ('zp-leak',b'\x68\x95\x06\xe8',2,7),
                                 ('shell-stack',b'\xa9\x4f\x85\x07',1,0xef)):
        if gate.count(pattern)!=1:raise ValueError('ambiguous fault '+name)
        offset=normal.index(gate)+gate.index(pattern)+delta
        bad=bytearray(normal);old=bad[offset];bad[offset]=new
        (WORK / f'probe-{name}.prg').write_bytes(bad)
        controls[name]={'offset':offset,'before':old,'after':new}
    objects,segments=parse_map((WORK / 'module.map').read_text())
    paths=list(SOURCE.iterdir())+[Path(__file__),OLD / 'driver.s',OLD / 'probe.cfg',OLD / 'gateway.cfg',
        ROOT / 'bench/window-cache-overlay/core.s',ROOT / 'bench/graphics-raster/launcher.s',
        ROOT / 'include/udeks/window_cache_command.h',ROOT / 'include/udeks/window_cache_state.h',
        ROOT / 'src/services/window/cache_overlay.c',ROOT / 'src/services/window/move_cache_state.c']
    linked=('module.bin','module-envelope.bin','module.map','gateway.bin','driver.s','launcher.s',
            'probe-0.bin','probe-0.map','probe-1.bin','probe-1.map')
    report={'qualification':'standalone combined command lease; not installed or NMI-qualified',
        'module_bytes':len(module),'module_segments':{n:[s,e] for n,s,e in segments},
        'command_object':object_sizes(WORK / 'command.o'),
        'binding_object':object_sizes(WORK / 'binding.o'),'gateway_bytes':len(gate),
        'private_stack':[0x4f00,0x4fef],'image':[0x5000,0x5bff],
        'remaining_resident_padding':516-object_sizes(WORK / 'binding.o')['CODE'],
        'negative_controls':controls,'helpers':sorted(n for n in objects if 'none.lib(' in n),
        'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in paths if p.is_file()},
        'linked_sha256':{n:digest(WORK / n) for n in linked},
        'program_sha256':{p.name:digest(p) for p in sorted(WORK.glob('probe-*.prg'))}}
    (WORK / 'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if not k.endswith('sha256')},indent=2))

def reference(case):
    from window_cache_c_runtime import reference as old_reference
    if case==0:return old_reference(0)
    original=bytes((i*13+7)&255 for i in range(8000))
    bitmap=bytearray((i*31+19)&255 for i in range(8000));dirty=bytearray(32)
    for xx,yy in ((100,40),(151,83)):
        for row in range(104):
            for col in range(168):
                sx,sy,dx,dy=7+col,7+row,xx+col,yy+row
                so=(sy//8)*320+(sx//8)*8+sy%8
                dest=(dy//8)*320+(dx//8)*8+dy%8;mask=128>>(dx%8)
                if original[so]&(128>>(sx%8)):bitmap[dest]|=mask
                else:bitmap[dest]&=255^mask
                dirty[dest//256]=1
    return bytes(bitmap+dirty)

def facts(data,case):
    if case not in (0,1) or len(data)!=8096 or data[:8]!=b'CMND\x01\x02'+bytes((case,0)):
        raise ValueError('command header/semantic failure')
    rows,calls,images=(132,543,66) if case==0 else (312,336,2)
    if (int.from_bytes(data[8:10],'little'),int.from_bytes(data[10:12],'little'),data[14])!=(rows,calls,images):
        raise ValueError('incomplete commands/rows/images')
    irq=int.from_bytes(data[12:14]+data[24:26],'little')
    if not irq or data[23]!=15 or any(data[26:64]) or data[64:]!=reference(case):
        raise ValueError('IRQ/flags/reserved/pixel oracle failed')
    return rows,calls,images,irq

def decode(data,case):
    rows,calls,images,irq=facts(data,case)
    if any(data[15:22]) or not 0x40<=data[22]<0xf0:raise ValueError('runtime/guard failure')
    return {'rows':rows,'commands':calls,'images':images,'interrupts':irq,
            'observed_stack_offset':data[22],'pixel_sha256':hashlib.sha256(data[64:]).hexdigest()}

def negative(data,name):
    facts(data,0)
    required={'irq-leak':(15,), 'zp-leak':(16,), 'shell-stack':(19,21)}[name]
    if any(data[i]!=(1 if i in required else 0) for i in range(15,22)):
        raise ValueError('missing/unexpected fault '+name)
    if name=='shell-stack' and data[22]!=0xf0:raise ValueError('wrong private stack use')
    if name!='shell-stack' and not 0x40<=data[22]<0xf0:raise ValueError('unexercised private stack')
    return {'detected_fields':list(required)}

def verify(report):
    for key,base in (('source_sha256',ROOT),('linked_sha256',WORK),('program_sha256',WORK)):
        for n,sha in report[key].items():
            if digest(base / n)!=sha:raise ValueError('input drift '+n)

def run(engine,output,emulator):
    from graphics_raster_bench_run import emulator_provenance
    report=json.loads((WORK / 'build-report.json').read_text());verify(report)
    output.mkdir(parents=True,exist_ok=True)
    if engine=='1986':
        sources=importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
        provenance=emulator_provenance(emulator,sources)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
        runner=WORK / '1986-command'
        subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator / 'src'),
            str(ROOT / 'tools/1986_raster_bench.c'),*map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    else:
        provenance=subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True)
    decoded={};raw_hashes={}
    for case in (0,1,'irq-leak','zp-leak','shell-stack'):
        program=WORK / f'probe-{case}.prg';raw=output / f'{engine}-{case}.bin'
        cmd=([str(runner),str(program),str(raw),'CMND'] if engine=='1986' else
             ['python3',str(ROOT / 'tools/vice_capture.py'),str(program),str(raw),
              '--entry','0x2000','--raw-load','--result-address','0x7fc0',
              '--result-size','8096','--state-offset','5','--timeout','90'])
        subprocess.run(cmd,check=True)
        decoded[str(case)]=decode(raw.read_bytes(),case) if isinstance(case,int) else negative(raw.read_bytes(),case)
        raw_hashes[raw.name]=digest(raw);print(json.dumps(decoded[str(case)]),flush=True)
    verify(report)
    if engine=='1986' and emulator_provenance(emulator,sources)!=provenance:raise ValueError('emulator drift')
    (output / f'{engine}-run.json').write_text(json.dumps({'program_sha256':report['program_sha256'],
        'raw_sha256':raw_hashes,'decoded':decoded,'provenance':provenance},indent=2)+'\n')

def preserve(output):
    report=json.loads((WORK / 'build-report.json').read_text());verify(report)
    reports={}
    for engine in ('1986','vice'):
        r=json.loads((output / f'{engine}-run.json').read_text())
        if r['program_sha256']!=report['program_sha256']:raise ValueError('wrong executable')
        expected={f'{engine}-{c}.bin' for c in (0,1,'irq-leak','zp-leak','shell-stack')}
        if set(r['raw_sha256'])!=expected:raise ValueError('incomplete run')
        for n,sha in r['raw_sha256'].items():
            if digest(output / n)!=sha:raise ValueError('record drift')
        reports[engine]={str(c):decode((output / f'{engine}-{c}.bin').read_bytes(),c) if isinstance(c,int)
            else negative((output / f'{engine}-{c}.bin').read_bytes(),c)
            for c in (0,1,'irq-leak','zp-leak','shell-stack')}
        if r['decoded']!=reports[engine]:raise ValueError('decoded drift')
    artifacts=ROOT / 'bench/artifacts' / NAME;results=ROOT / 'bench/results' / NAME
    if artifacts.exists() or results.exists():raise ValueError('refusing to overwrite evidence')
    artifacts.mkdir(parents=True);results.mkdir(parents=True)
    for n in report['source_sha256']:
        target=artifacts / n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT / n,target)
    dest=artifacts / 'build';dest.mkdir()
    for n in set(report['linked_sha256'])|set(report['program_sha256'])|{'build-report.json'}:
        shutil.copy2(WORK / n,dest / n)
    for p in output.iterdir():
        if p.suffix in ('.bin','.json'):shutil.copy2(p,results / p.name)
    (results / 'report.json').write_text(json.dumps(reports,indent=2)+'\n')
    for directory in (artifacts,results):
        paths=sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('build','run','preserve'))
    p.add_argument('--engine',choices=('1986','vice'))
    p.add_argument('--output',type=Path,default=ROOT / 'build/bench/window-cache-command-results')
    p.add_argument('--emulator',type=Path,default=ROOT.parent / '1986')
    a=p.parse_args()
    if a.action=='build':build()
    elif a.action=='preserve':preserve(a.output)
    else:
        if a.engine is None:p.error('run requires --engine')
        run(a.engine,a.output,a.emulator)

if __name__=='__main__':main()

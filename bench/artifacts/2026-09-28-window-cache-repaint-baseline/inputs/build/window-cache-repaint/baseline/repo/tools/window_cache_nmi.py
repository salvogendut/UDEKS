#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the exact common NMI stub during the combined C cache lease."""
import argparse
import hashlib
import importlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path
import window_cache_command as base

ROOT=base.ROOT
WORK=ROOT / 'build/bench/window-cache-nmi'
NAME='2026-09-28-window-cache-nmi'
CASES=(0,1,'no-pending')

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def build():
    from graphics_span_bench import object_sizes
    base.build()
    WORK.mkdir(parents=True,exist_ok=True)
    driver=(base.WORK / 'driver.s').read_text()
    driver=driver.replace('.import _private_cache_policy_call',
                          '.import _udeks_nmi_drain\n        .import _private_cache_policy_call')
    old='mapped:\n        lda $dc0d'
    if driver.count(old)!=1:raise ValueError('diagnostic IRQ mapping seam changed')
    driver=driver.replace(old,'mapped:\n        jsr _udeks_nmi_drain\n        lda $dc0d')
    (WORK / 'driver.s').write_text(driver)
    source=(base.SOURCE / 'probe.c').read_text()
    old="V(RECORD)='C';V(RECORD+1)='M';V(RECORD+2)='N';V(RECORD+3)='D';"
    if source.count(old)!=1:raise ValueError('record publication changed')
    source=source.replace(old,"V(RECORD)='N';V(RECORD+1)='M';V(RECORD+2)='I';V(RECORD+3)='C';")
    source='extern void nmi_probe_start(void),nmi_probe_stop(void),nmi_probe_publish(void);\n'+source
    source=source.replace('runtime_irq_start();preflight();','runtime_irq_start();nmi_probe_start();preflight();')
    source=source.replace('runtime_irq_stop();','runtime_irq_stop();nmi_probe_stop();')
    source=source.replace('V(RECORD+5)=2;return 0;','nmi_probe_publish();V(RECORD+5)=2;return 0;')
    (WORK / 'probe.c').write_text(source)
    for name,path in (('driver',WORK / 'driver.s'),('nmi',ROOT / 'src/8502/nmi.s'),
                      ('observer',ROOT / 'bench/window-cache-nmi/probe.s')):
        subprocess.run(['ca65','-I',str(base.SOURCE),'-I',str(ROOT / 'src/8502'),
            '-o',str(WORK / (name+'.o')),str(path)],check=True)
    for case in (0,1):
        stem=WORK / f'probe-{case}'
        subprocess.run(['cl65','-t','none','--standard','c99','-Oirs','-D',f'CASE={case}',
            '-c','-o',str(stem.with_suffix('.o')),str(WORK / 'probe.c')],check=True)
        subprocess.run(['cl65','-t','none','-C',str(base.OLD / 'probe.cfg'),
            '-m',str(stem.with_suffix('.map')),'-o',str(stem.with_suffix('.bin')),
            str(base.WORK / 'launcher.o'),str(stem.with_suffix('.o')),str(WORK / 'driver.o'),
            str(base.WORK / 'binding.o'),str(WORK / 'nmi.o'),str(WORK / 'observer.o')],check=True)
        stem.with_suffix('.prg').write_bytes(b'\x00\x20'+stem.with_suffix('.bin').read_bytes())
    stub=b'\x48\xa9\x01\x8d\xf5\xff\x68\x40'
    program=(WORK / 'probe-0.prg').read_bytes()
    if program.count(stub)!=1:raise ValueError('exact production NMI stub not unique')
    offset=program.index(stub)+3
    bad=bytearray(program);bad[offset]=0x2c # BIT, not STA: no deferred pending flag
    (WORK / 'probe-no-pending.prg').write_bytes(bad)
    base_report=json.loads((base.WORK / 'build-report.json').read_text())
    paths={n:ROOT / n for n in base_report['source_sha256']}
    paths.update({str(p.relative_to(ROOT)):p for p in (Path(__file__),ROOT / 'src/8502/nmi.s',
        ROOT / 'src/8502/nmi-common.inc',ROOT / 'bench/window-cache-nmi/probe.s',
        ROOT / 'tools/window_cache_command.py',ROOT / 'tools/1986_raster_bench.c',
        ROOT / 'tools/1986_input_smoke_build.py',ROOT / 'tools/graphics_raster_bench_run.py',
        ROOT / 'tools/vice_capture.py')})
    # Include the reused module/binding inputs rather than silently depending
    # on whatever another benchmark last left under build/.
    linked={f'base/{n}':base.WORK / n for n in ('module.bin','module-envelope.bin','module.map',
        'gateway.bin','launcher.s','build-report.json')}
    linked.update({n:WORK / n for n in ('driver.s','probe.c','probe-0.bin','probe-0.map','probe-1.bin','probe-1.map')})
    for name,path in list(linked.items()):
        if name.startswith('base/'):
            dest=WORK / name;dest.parent.mkdir(exist_ok=True);shutil.copy2(path,dest);linked[name]=dest
    report={'qualification':'NMI/C-cache standalone proof; no live GUI/Z80/hardware qualification',
        'nmi_object':object_sizes(WORK / 'nmi.o'),'stub_hex':stub.hex(),
        'cc65':subprocess.check_output(['cc65','--version'],stderr=subprocess.STDOUT,text=True).strip(),
        'negative_control':{'offset':offset,'before':0x8d,'after':0x2c},
        'source_sha256':{n:digest(p) for n,p in paths.items()},
        'linked_sha256':{n:digest(p) for n,p in linked.items()},
        'program_sha256':{f'probe-{c}.prg':digest(WORK / f'probe-{c}.prg') for c in CASES}}
    (WORK / 'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'nmi_object':report['nmi_object'],'stub_hex':report['stub_hex']},indent=2))

def facts(data,case):
    if len(data)!=8096 or data[:4]!=b'NMIC':raise ValueError('NMI record signature')
    normalized=bytearray(data);normalized[:4]=b'CMND';normalized[26:38]=bytes(12)
    normal=base.decode(normalized,case)
    total=int.from_bytes(data[26:30],'little');worker=int.from_bytes(data[30:34],'little')
    drains=int.from_bytes(data[34:36],'little')
    if not total or worker>total or data[36] or data[37]:raise ValueError('NMI event/guard failure')
    return {**normal,'nmi_total':total,'nmi_worker_flat':worker,'nmi_drains':drains}

def decode(data,case):
    r=facts(data,case)
    if not 0<r['nmi_worker_flat']<r['nmi_total']<65536 or r['nmi_total']!=r['nmi_drains']:
        raise ValueError('worker/kernel NMI and deferred drain not qualified')
    return r

def negative(data):
    r=facts(data,0)
    if r['nmi_total']!=1 or r['nmi_drains']!=0:raise ValueError('pending fault not detected')
    try:decode(data,0)
    except ValueError:pass
    else:raise ValueError('negative passed positive decoder')
    return r

def verify(r):
    for key,root in (('source_sha256',ROOT),('linked_sha256',WORK),('program_sha256',WORK)):
        for n,sha in r[key].items():
            if digest(root / n)!=sha:raise ValueError('input drift '+n)

def run(engine,output):
    from graphics_raster_bench_run import emulator_provenance
    r=json.loads((WORK / 'build-report.json').read_text());verify(r);output.mkdir(parents=True,exist_ok=True)
    if engine=='1986':
        emulator=ROOT.parent / '1986';sources=importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
        provenance=emulator_provenance(emulator,sources)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
        runner=WORK / '1986-nmi'
        subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator / 'src'),
            str(ROOT / 'tools/1986_raster_bench.c'),*map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    else:provenance=subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True)
    decoded={};raw={}
    for case in CASES:
        program=WORK / f'probe-{case}.prg';path=output / f'{engine}-{case}.bin'
        cmd=([str(runner),str(program),str(path),'NMIC'] if engine=='1986' else
            ['python3',str(ROOT / 'tools/vice_capture.py'),str(program),str(path),
             '--entry','0x2000','--raw-load','--result-address','0x7fc0','--result-size','8096',
             '--state-offset','5','--timeout','90'])
        subprocess.run(cmd,check=True)
        decoded[str(case)]=decode(path.read_bytes(),case) if isinstance(case,int) else negative(path.read_bytes())
        raw[path.name]=digest(path);print(json.dumps(decoded[str(case)]),flush=True)
    verify(r)
    if engine=='1986' and emulator_provenance(emulator,sources)!=provenance:raise ValueError('emulator drift')
    (output / f'{engine}-run.json').write_text(json.dumps({'program_sha256':r['program_sha256'],
        'raw_sha256':raw,'decoded':decoded,'provenance':provenance},indent=2)+'\n')

def preserve(output):
    r=json.loads((WORK / 'build-report.json').read_text());verify(r)
    for engine in ('1986','vice'):
        run=json.loads((output / f'{engine}-run.json').read_text())
        if run['program_sha256']!=r['program_sha256']:raise ValueError('run/program mismatch')
        if set(run['raw_sha256'])!={f'{engine}-{c}.bin' for c in CASES}:raise ValueError('missing run')
        for n,sha in run['raw_sha256'].items():
            if digest(output / n)!=sha:raise ValueError('raw drift')
        for c in CASES:
            value=decode((output / f'{engine}-{c}.bin').read_bytes(),c) if isinstance(c,int) else negative((output / f'{engine}-{c}.bin').read_bytes())
            if value!=run['decoded'][str(c)]:raise ValueError('decoded drift')
    a=ROOT / 'bench/artifacts' / NAME;b=ROOT / 'bench/results' / NAME
    if a.exists() or b.exists():raise ValueError('refusing to overwrite evidence')
    a.mkdir(parents=True);b.mkdir(parents=True)
    for n in r['source_sha256']:
        dest=a / n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT / n,dest)
    for n in set(r['linked_sha256'])|set(r['program_sha256'])|{'build-report.json'}:
        dest=a / 'build' / n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(WORK / n,dest)
    for p in output.iterdir():
        if p.suffix in ('.bin','.json'):shutil.copy2(p,b / p.name)
    for directory in (a,b):
        paths=sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('build','run','preserve'))
    p.add_argument('--engine',choices=('1986','vice'))
    p.add_argument('--output',type=Path,default=ROOT / 'build/bench/window-cache-nmi-results')
    a=p.parse_args()
    if a.action=='build':build()
    elif a.action=='preserve':preserve(a.output)
    else:
        if a.engine is None:p.error('run requires --engine')
        run(a.engine,a.output)

if __name__=='__main__':main()

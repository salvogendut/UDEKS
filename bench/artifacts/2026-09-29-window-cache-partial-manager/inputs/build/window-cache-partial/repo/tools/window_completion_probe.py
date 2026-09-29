#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify installed completion notification without claiming cached GUI moves."""
import argparse
import hashlib
import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT / 'build/window-completion'
NAME='2026-09-28-window-completion'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def window_base(text):
    from placement_audit import parse_map
    match=re.search(r'^window_manager.o:\n(?:(?!^\S).*\n)*?\s+HIGHBSS\s+Offs=([0-9A-F]{6})\s+Size=000058',text,re.M)
    if not match:raise ValueError('manager private layout changed')
    segment={n:(s,e) for n,s,e in parse_map(text)[1]}['HIGHBSS']
    return segment[0]+int(match[1],16)

def inspect(windows,gateway,entry):
    if len(windows)!=88 or len(gateway)!=175 or gateway[:8]!=b'UAPP\x00\x03\x35\x03':
        raise ValueError('manager/gateway layout changed')
    if int.from_bytes(gateway[8:10],'little')!=entry or any(gateway[10:16]):
        raise ValueError('optional entry/reserved bytes changed')
    if any(gateway[16+i*3]!=0x4c for i in range(53)):
        raise ValueError('published JMP vector changed')
    owners=[]
    for slot in range(4):
        w=windows[slot*17:(slot+1)*17]
        if w[0]:owners.append(w[1])
        if w[0] and w[1]==2:
            if w[2]!=1 or w[3]!=0x8f or w[10]!=2:
                raise ValueError('wave lacks explicit topmost completion')
    if sorted(owners)!=[1,2]:raise ValueError('clock/wave not both live')
    return {'owners':owners,'wave_complete':True,'gateway_entry':entry}

def build():
    from gen_capability_imports import map_exports
    WORK.mkdir(parents=True,exist_ok=True)
    mapfile=ROOT / 'build/8502/udeks-8502.map';text=mapfile.read_text()
    base=window_base(text);entry=map_exports(text)['_udeks_window_image_complete'][0]
    source=(ROOT / 'tools/1986_input_smoke.c').read_text()
    needle='    unsigned cached_leases = word(0xF26C);'
    check=f'''    for (unsigned n=0;n<10000 &&
         (byte(0x{base+20:04X})!=0x8f || byte(0xF27A)!=21);++n) frames(1);
    require(byte(0x{base+20:04X})==0x8f, "wave completion notification missing");
    require(byte(0xF27A)==21, "partial image certified");
    printf("completion: explicit topmost image certified\\n");
'''
    if source.count(needle)!=1:raise ValueError('pre-drag seam changed')
    source=source.replace(needle,check+needle)
    needle='    require(byte(0xF11B) == 0, "lifecycle canary failures");'
    after=f'''{check}    require(word(0xF26C)==cached_leases, "completion re-acquired Z80");
'''
    if source.count(needle)!=1:raise ValueError('post-drag seam changed')
    source=source.replace(needle,after+needle)
    (WORK / 'native.c').write_text(source)
    inputs=[mapfile,ROOT / 'build/user/xwave.bin',ROOT / 'build/user/xclock.bin',
        ROOT / 'build/user/bootfs.img',ROOT / 'build/8502/udeks-8502.bin',
        ROOT / 'src/services/window/window_manager.c',ROOT / 'include/udeks/window.h',
        ROOT / 'src/8502/app_gateway.s',ROOT / 'src/apps/xwave.c',
        ROOT / 'user/lib/window_completion.s',ROOT / 'tools/1986_input_smoke.c',
        ROOT / 'tools/1986_input_smoke_build.py',Path(__file__),ROOT / 'Makefile']
    report={'qualification':'installed completion only; moves still redraw',
        'window_base':base,'completion_entry':entry,
        'resident_charge':158,'remaining_padding':358,'bootfs_free':0,
        'disk_sha256':{fmt:digest(ROOT / 'build/boot' / f'udeks.{fmt}') for fmt in ('d71','d64')},
        'inputs_sha256':{str(p.relative_to(ROOT)):digest(p) for p in inputs},'native_sha256':digest(WORK / 'native.c')}
    (WORK / 'build-report.json').write_text(json.dumps(report,indent=2)+'\n')

def verify(r):
    for n,sha in r['inputs_sha256'].items():
        if digest(ROOT / n)!=sha:raise ValueError('source/build drift '+n)
    for fmt,sha in r['disk_sha256'].items():
        if digest(ROOT / 'build/boot' / f'udeks.{fmt}')!=sha:raise ValueError('disk drift')
    if digest(WORK / 'native.c')!=r['native_sha256']:raise ValueError('harness drift')

def native():
    from bench_decode import extract_memory
    from graphics_raster_bench_run import emulator_provenance
    r=json.loads((WORK / 'build-report.json').read_text());verify(r)
    emulator=ROOT.parent / '1986';builder=importlib.import_module('1986_input_smoke_build')
    sources=builder.emulator_sources(emulator);provenance=emulator_provenance(emulator,sources)
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
    runner=WORK / 'native'
    subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator / 'src'),str(WORK / 'native.c'),
        *map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    decoded={}
    for fmt in ('d71','d64'):
        snapshot=WORK / f'1986-{fmt}.vsf'
        cmd=[str(runner),str(emulator / 'roms'),str(ROOT / 'build/boot' / f'udeks.{fmt}'),
            builder.slot_address(ROOT / 'build/8502/udeks-scheduler-overlay.map'),str(snapshot)]
        p=subprocess.run(cmd,capture_output=True,text=True)
        (WORK / f'1986-{fmt}.log').write_text(p.stdout+p.stderr)
        print(p.stdout,flush=True)
        if p.returncode:raise ValueError('native qualification failed')
        memory=snapshot.read_bytes()
        w=extract_memory(memory,r['window_base'],88);g=extract_memory(memory,0xcf50,175)
        (WORK / f'1986-{fmt}-windows.bin').write_bytes(w)
        (WORK / f'1986-{fmt}-gateway.bin').write_bytes(g)
        decoded[fmt]=inspect(w,g,r['completion_entry'])
    if emulator_provenance(emulator,sources)!=provenance:raise ValueError('emulator drift')
    verify(r)
    raw={p.name:digest(p) for p in WORK.glob('1986-*') if p.suffix in ('.bin','.log')}
    (WORK / '1986-run.json').write_text(json.dumps({'provenance':provenance,'decoded':decoded,
        'build_report_sha256':digest(WORK / 'build-report.json'),'raw_sha256':raw},indent=2)+'\n')

def vice():
    import shadow_boot_probe as sp
    from capability_relocation_probe import inject_until_state
    from vice_capture import choose_port
    r=json.loads((WORK / 'build-report.json').read_text());verify(r)
    symbols=sp.symbol_addresses(ROOT / 'build/8502/udeks-8502.map');decoded={}
    provenance=subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True)
    for fmt in ('d71','d64'):
        port=choose_port();process,master=sp.launch_vice(ROOT / 'build/boot' / f'udeks.{fmt}',port,'net.sf.VICE')
        try:
            time.sleep(6);deadline=time.monotonic()+180
            sp.wait_for_byte(port,sp.ROOT_TERMINAL_STATUS_READY_ADDRESS,2,deadline)
            for command,address,state in (('xinit',0xf1b5,3),('xclock &',0xf225,3),('xwave &',0xf265,3)):
                inject_until_state(port,symbols,command,address,state,deadline)
            sp.wait_for_byte(port,0xf27a,21,deadline)
            sp.wait_for_byte(port,r['window_base']+20,0x8f,deadline)
            w,g=sp.capture_blocks(port,[(WORK / f'vice-{fmt}-windows.bin',r['window_base'],r['window_base']+87,'kernel'),
                (WORK / f'vice-{fmt}-gateway.bin',0xcf50,0xcffe,'kernel')])
            # capture_blocks returns header-free bytes; save explicitly.
            (WORK / f'vice-{fmt}-windows.bin').write_bytes(w)
            (WORK / f'vice-{fmt}-gateway.bin').write_bytes(g)
            decoded[fmt]=inspect(w,g,r['completion_entry'])
            print(fmt,decoded[fmt],flush=True)
        finally:
            sp.terminate(process,port);os.close(master)
    verify(r)
    raw={p.name:digest(p) for p in WORK.glob('vice-*.bin')}
    (WORK / 'vice-run.json').write_text(json.dumps({'provenance':provenance,'decoded':decoded,
        'build_report_sha256':digest(WORK / 'build-report.json'),'raw_sha256':raw},indent=2)+'\n')

def preserve():
    r=json.loads((WORK / 'build-report.json').read_text());verify(r)
    for engine in ('1986','vice'):
        run=json.loads((WORK / f'{engine}-run.json').read_text())
        if run['build_report_sha256']!=digest(WORK / 'build-report.json'):
            raise ValueError('run/build mismatch')
        expected={f'{engine}-{fmt}-{kind}.bin' for fmt in ('d71','d64') for kind in ('windows','gateway')}
        if engine=='1986':expected|={f'1986-{fmt}.log' for fmt in ('d71','d64')}
        if set(run['raw_sha256'])!=expected:raise ValueError('missing raw records')
        for n,sha in run['raw_sha256'].items():
            if digest(WORK / n)!=sha:raise ValueError('raw record drift')
        for fmt in ('d71','d64'):
            actual=inspect((WORK / f'{engine}-{fmt}-windows.bin').read_bytes(),
                           (WORK / f'{engine}-{fmt}-gateway.bin').read_bytes(),r['completion_entry'])
            if actual!=run['decoded'][fmt]:raise ValueError('decoded drift')
    a=ROOT / 'bench/artifacts' / NAME;b=ROOT / 'bench/results' / NAME
    if a.exists() or b.exists():raise ValueError('refusing to overwrite evidence')
    a.mkdir(parents=True);b.mkdir(parents=True)
    for n in r['inputs_sha256']:
        dest=a / n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT / n,dest)
    for fmt in ('d71','d64'):
        shutil.copy2(ROOT / 'build/boot' / f'udeks.{fmt}',a / f'udeks.{fmt}')
    for n in ('native.c','build-report.json'):shutil.copy2(WORK / n,a / n)
    for p in WORK.iterdir():
        if p.name.startswith(('1986-','vice-')) and p.suffix in ('.bin','.json','.log'):shutil.copy2(p,b / p.name)
    for directory in (a,b):
        paths=sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('build','1986','vice','preserve'));a=p.parse_args()
    {'build':build,'1986':native,'vice':vice,'preserve':preserve}[a.action]()

if __name__=='__main__':main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify streaming XVIEW using unmodified 1986, native keyboard and mouse."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
from gen_capability_imports import map_exports
from build_scheduler_overlay import map_segments
from png_to_cbm import build
import build_d81

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('emulator','roms','disk','pictures','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();work=args.output.resolve();work.mkdir(parents=True,exist_ok=False)
    emulator=args.emulator.resolve()
    spec=importlib.util.spec_from_file_location('smoke',ROOT/'tools/1986_input_smoke_build.py')
    smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
    kernel=(ROOT/'build/8502/udeks-8502.map').read_text();exports=map_exports(kernel)
    app=map_exports((ROOT/'build/xview/xview.map').read_text())
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
    defines=['-DUDEKS_XVIEW_SMOKE','-DUDEKS_DISK_GRAPHICS_SMOKE','-DUDEKS_SMOKE_DRIVE=1581',
        '-DUDEKS_CONSOLE_BASE='+str(map_segments(kernel)['LOWBSS'][0]),
        '-DUDEKS_XVIEW_LENGTHS='+str(exports['_udeks_retained_lengths'][0])]
    for name in ('ready','uploaded'):
        defines.append('-DUDEKS_XVIEW_'+name.upper()+'='+str(app['_xview_'+name][0]-0x1000))
    binary=work/'smoke'
    subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator/'src'),*defines,
        str(ROOT/'tools/1986_storage_smoke.c'),*map(str,smoke.emulator_sources(emulator)),
        *flags,'-lm','-o',str(binary)],check=True)
    fixtures={'BAD':b'CBM\0\2'+bytes(7),'TRAIL':build(b'\x80',1,1)+b'X',
        'PAD':build(b'\x80',1,1)[:-1]+b'\x81','BIG':build(bytes(8000),320,200),
        'TRUNC':build(b'\xff'*1280,128,80)[:-1],
        'ODD':build(b'\xaa\x80'*7,9,7),'DENSE':build(b'\xff'*816,128,51)}
    picture_dir=work/'pictures';picture_dir.mkdir()
    for name in ('ALEX128','CLOCK160'):
        (picture_dir/(name+'.CBM')).write_bytes((args.pictures/(name+'.CBM')).read_bytes())
    for name in ('CLOCKWORK','ALEX2'):
        (picture_dir/(name+'.CBM')).write_bytes((ROOT/'PICS'/(name+'.CBM')).read_bytes())
    source=args.disk.read_bytes();image=bytearray(source)
    for name,data in fixtures.items():
        build_d81.install_file(image,name+'.CBM',data,file_type=0x81)
        (picture_dir/(name+'.CBM')).write_bytes(data)
    disk=work/'test.d81';disk.write_bytes(image)
    environment=dict(os.environ,UDEKS_XVIEW_OUTPUT=str(work),UDEKS_XVIEW_PICTURES=str(picture_dir))
    with (work/'run.log').open('w') as log:
        result=subprocess.run([str(binary),str(args.roms.resolve()),str(disk),
            smoke.slot_address(ROOT/'build/8502/udeks-scheduler-overlay.map'),str(work/'result.vsf')],
            stdout=log,stderr=subprocess.STDOUT,env=environment)
    if disk.read_bytes()!=image or args.disk.read_bytes()!=source:raise AssertionError('viewer wrote disk')
    report=dict(exit_status=result.returncode,drive=1581,
        disk_sha256=hashlib.sha256(source).hexdigest(),fixture_sha256=hashlib.sha256(image).hexdigest(),
        app_sha256=hashlib.sha256((ROOT/'build/xview/XVIEW.BIN').read_bytes()).hexdigest(),
        emulator_revision=subprocess.check_output(['git','-C',str(emulator),'rev-parse','HEAD'],text=True).strip(),
        emulator_tracked_changes=subprocess.check_output(['git','-C',str(emulator),'status','--porcelain','--untracked-files=no'],text=True).strip())
    (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));raise SystemExit(result.returncode)


if __name__=='__main__':main()

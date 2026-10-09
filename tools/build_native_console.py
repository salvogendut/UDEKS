#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build an independent cooperative console probe; no kernel/map imports.

This first SDK has stdout/stderr and bounded sleep, not argc delivery, stdin
ownership or background output arbitration. Use a foreground bare command.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

from build_graphical_example import check_native_capacity
from gen_capability_imports import map_exports
from native_app_layout import fitting_allocations
from o65_to_udex import pack_o65

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'user/examples/ticker.c')
    parser.add_argument('--name',default='TICKER')
    parser.add_argument('--output',type=Path,default=ROOT/'build/native-console/ticker')
    parser.add_argument('--export',action='append',default=[],dest='exports')
    args=parser.parse_args()
    name=args.name.upper()
    if not re.fullmatch(r'[A-Z0-9_-]{1,12}',name): parser.error('invalid executable name')
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',n) for n in args.exports):
        parser.error('invalid export')
    out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    (out/(name+'.BIN')).unlink(missing_ok=True)
    def run(*cmd): subprocess.run(cmd,cwd=ROOT,check=True)
    objects=[]
    for label,source in (('program',args.source),('runtime',ROOT/'user/lib/native_console.c')):
        run('cc65','-t','none','--cpu','6502','--standard','c99','-Os',
            '-I','user/include','-I','include','-o',str(out/(label+'.s')),str(source.resolve()))
        run('ca65','--cpu','6502','-o',str(out/(label+'.o')),str(out/(label+'.s')))
        objects.append(str(out/(label+'.o')))
    run('ca65','--cpu','6502','-o',str(out/'entry.o'),'user/lib/native_console_entry.s')
    options=[p for symbol in dict.fromkeys(['_udeks_program_entry',*args.exports]) for p in ('-u',symbol)]
    run('cl65','-t','none','--cpu','6502','-C','cfg/8502-reloc-app.cfg',*options,
        '-m',str(out/'program.map'),'-o',str(out/'program.o65'),str(out/'entry.o'),*objects)
    entry=map_exports((out/'program.map').read_text())['_udeks_program_entry'][0]
    image=pack_o65((out/'program.o65').read_bytes(),entry)
    check_native_capacity(image)
    (out/(name+'.BIN')).write_bytes(image)
    size,bss=(int.from_bytes(image[n:n+2],'little') for n in (10,12))
    result=dict(file=len(image),image=size,bss=bss,fits=fitting_allocations(image),
                joined_fits=fitting_allocations(image,joined=True),resident_bytes=0,
                scope='foreground stdout/stderr/sleep probe; no arguments or stdin yet')
    (out/'layout.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()

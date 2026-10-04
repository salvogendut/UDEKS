#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a separately linked graphical example, without rebuilding the OS."""
import argparse
from pathlib import Path
import subprocess
from gen_capability_imports import map_exports
from o65_to_udex import pack_o65

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/generic-apps/example')
    args=parser.parse_args()
    out=args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    def run(*args): subprocess.run(args, cwd=ROOT, check=True)
    run('cc65','-t','none','--cpu','6502','--standard','c99','-Os','-I','include',
        '-o',str(out/'xhello.s'),'user/examples/xhello.c')
    objects=[]
    for name,path in (('entry','user/lib/native_graphics_entry.s'),
                      ('request','user/lib/graphics_request.s'),('xhello',out/'xhello.s')):
        obj=out/(name+'.o'); objects.append(str(obj))
        run('ca65','--cpu','6502','-o',str(obj),str(path))
    run('cl65','-t','none','--cpu','6502','-C','cfg/8502-reloc-app.cfg',
        '-u','_udeks_program_entry','-u','_hello_clicks',
        '-m',str(out/'xhello.map'),'-o',str(out/'xhello.o65'),*objects)
    entry=map_exports((out/'xhello.map').read_text())['_udeks_program_entry'][0]
    image=pack_o65((out/'xhello.o65').read_bytes(), entry)
    (out/'HELLO.BIN').write_bytes(image)
    print('Independent HELLO.BIN:',len(image),'bytes')

if __name__=='__main__': main()

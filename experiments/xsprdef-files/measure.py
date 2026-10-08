#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile only; never install this oversized, unqualified prototype on disks."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from gen_capability_imports import map_exports
from o65_to_udex import pack_o65

def main():
    out=ROOT/'build/sprite-files/prototype'
    out.mkdir(parents=True,exist_ok=True)
    def run(*args): subprocess.run(args,cwd=ROOT,check=True)
    objects=[]
    for name in ('xsprdef','xspr_file'):
        run('cc65','-t','none','--cpu','6502','--standard','c99','-Os',
            '--static-locals','-I','include','-o',str(out/(name+'.s')),str(HERE/(name+'.c')))
    for name,path in (('entry',ROOT/'user/lib/native_graphics_entry.s'),
                      ('request',HERE/'graphics_request.s'),
                      ('xsprdef',out/'xsprdef.s'),('xspr_file',out/'xspr_file.s')):
        obj=out/(name+'.o');objects.append(str(obj))
        run('ca65','-D','UDEKS_GFX_ABI=15','-o',str(obj),str(path))
    run('cl65','-t','none','-C','cfg/8502-reloc-app.cfg','-u','_udeks_program_entry',
        '-m',str(out/'xsprdef.map'),'-o',str(out/'xsprdef.o65'),*objects)
    entry=map_exports((out/'xsprdef.map').read_text())['_udeks_program_entry'][0]
    image=pack_o65((out/'xsprdef.o65').read_bytes(),entry)
    allocation=sum(int.from_bytes(image[n:n+2],'little') for n in (10,12))
    print(f'PROTOTYPE ONLY: {len(image)} file bytes, {allocation} image+BSS bytes')
    print('Current maximum: 4608 file bytes, 4352 image+BSS bytes; NOT installed.')

if __name__=='__main__': main()

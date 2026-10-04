#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a separately linked graphical example, without rebuilding the OS."""
import argparse
from pathlib import Path
import re
import subprocess
from gen_capability_imports import map_exports
from o65_to_udex import pack_o65

ROOT=Path(__file__).resolve().parents[1]

def check_capacity(image,capacity):
    if capacity is not None:
        allocation=sum(int.from_bytes(image[n:n+2],'little') for n in (10,12))
        if not 0<capacity<=65535 or max(len(image),allocation)>capacity:
            raise ValueError('executable file or image+BSS exceeds the requested allocation')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/generic-apps/example')
    parser.add_argument('--source', type=Path, action='append',
                        help='C translation unit; repeat for a multi-file program')
    parser.add_argument('--name', default='HELLO', help='portable disk basename')
    parser.add_argument('--graphics-abi', type=int, choices=(9,10,11,12), default=9,
                        help='minimum request ABI; 10 resize, 11 worker calls, 12 retained paths')
    parser.add_argument('--static-locals', action='store_true',
                        help='cc65 private static locals; only for nonrecursive programs')
    parser.add_argument('--capacity',type=int,help='require both file and image+BSS to fit this many bytes')
    parser.add_argument('--export', action='append', default=[], dest='exports',
                        help='additional linker symbol to retain in the map')
    args=parser.parse_args()
    name=args.name.upper()
    if not re.fullmatch(r'[A-Z0-9_-]{1,12}',name): parser.error('invalid command name')
    sources=args.source or [ROOT/'user/examples/xhello.c']
    labels=[source.stem for source in sources]
    if len(set(labels))!=len(labels) or set(labels)&{'entry','request'}:
        parser.error('source basenames must be unique and not entry/request')
    exports=['_udeks_program_entry']+args.exports
    if args.source is None: exports.append('_hello_clicks')
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',symbol) for symbol in exports):
        parser.error('invalid exported symbol')
    out=args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    def run(*args): subprocess.run(args, cwd=ROOT, check=True)
    for label,source in zip(labels,sources):
        run('cc65','-t','none','--cpu','6502','--standard','c99','-Os',
            *(['--static-locals'] if args.static_locals else []),
            '-I','include','-I','user/include',
            '-o',str(out/(label+'.s')),str(source.resolve()))
    objects=[]
    for name,path in (('entry','user/lib/native_graphics_entry.s'),
                      ('request','user/lib/graphics_request.s'),
                      *((label,out/(label+'.s')) for label in labels)):
        obj=out/(name+'.o'); objects.append(str(obj))
        run('ca65','--cpu','6502','-D','UDEKS_GFX_ABI='+str(args.graphics_abi),
            '-o',str(obj),str(path))
    stem=labels[0]
    options=[option for symbol in dict.fromkeys(exports) for option in ('-u',symbol)]
    run('cl65','-t','none','--cpu','6502','-C','cfg/8502-reloc-app.cfg',
        *options,'-m',str(out/(stem+'.map')),'-o',str(out/(stem+'.o65')),*objects)
    entry=map_exports((out/(stem+'.map')).read_text())['_udeks_program_entry'][0]
    image=pack_o65((out/(stem+'.o65')).read_bytes(), entry)
    check_capacity(image,args.capacity)
    filename=args.name.upper()+'.BIN'
    (out/filename).write_bytes(image)
    print('Independent',filename+':',len(image),'bytes')

if __name__=='__main__': main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a standalone argc/argv console command without linking the kernel.

Override --source/--name for your own single-file C command. This uses the
existing synchronous UDEX 0.1 ABI, not the native graphical task runtime.
"""
import argparse
from pathlib import Path
import re
import subprocess
from build_udex import build_executable
from gen_capability_imports import map_exports

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'user/examples/args.c')
    parser.add_argument('--name', default='ARGS')
    parser.add_argument('--output', type=Path, default=ROOT/'build/generic-apps/console')
    parser.add_argument('--filesystem', action='store_true', help='link counted file I/O (UTRQ 0.14)')
    parser.add_argument('--file-mutations', action='store_true',
                        help='rename/copy/unlink SDK (requires UTRQ 0.18)')
    parser.add_argument('--static-locals', action='store_true', help='only for nonrecursive single-invocation programs')
    args = parser.parse_args()
    name = args.name.upper()
    if not re.fullmatch(r'[A-Z0-9_-]{1,12}', name): parser.error('invalid command name')
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    def run(*command): subprocess.run(command, cwd=ROOT, check=True)
    run('cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Os',
        *(['--static-locals'] if args.static_locals else []),
        '-I', 'user/include', '-I', 'include', '-o', str(out/'program.s'), str(args.source.resolve()))
    libraries=[]
    if args.filesystem or args.file_mutations:
        for label in ('filesystem0','filesystem1','filesystem2','filesystem3','filesystem_meta','error_string') + (('file_mutation0','file_mutation1','file_mutation2','file_mutation3') if args.file_mutations else ()):
            part = label[-1] if label[-1].isdigit() else None
            source = label[:-1] if part is not None else label
            run('cc65','-t','none','--cpu','6502','--standard','c99','-Os','--static-locals',
                *(['-D',('UDEKS_FS_PART=' if source=='filesystem' else 'UDEKS_MUTATION_PART=')+part] if part is not None else []),
                '-I','user/include','-I','include','-o',str(out/(label+'.s')), 'user/lib/'+source+'.c')
            libraries.append((label,out/(label+'.s')))
        libraries.append(('fs_request','user/lib/fs_request.s'))
        if args.file_mutations:
            libraries.append(('file_mutation_request', 'user/lib/file_mutation_request.s'))
    objects = []; members=[]
    for label, source in (('entry', 'user/lib/entry.s'), ('syscall', 'user/lib/syscall.s'),
                          ('program', out/'program.s'), *libraries):
        obj = out/(label+'.o')
        (members if label in {n for n,_ in libraries} else objects).append(str(obj))
        run('ca65', '--cpu', '6502', '-o', str(obj), str(source))
    if members:
        library=out/'filesystem.lib'
        library.unlink(missing_ok=True)  # generated archive, never a user source
        run('ar65','a',str(library),*members)
        objects.append(str(library))
    run('cl65', '-t', 'none', '--cpu', '6502', '-C', 'cfg/8502-user-app1.cfg',
        '-u', '_udeks_program_entry', '-u', '__BSS_SIZE__', '-m', str(out/'program.map'),
        '-o', str(out/'program.bin'), *objects)
    symbols = map_exports((out/'program.map').read_text())
    image = build_executable((out/'program.bin').read_bytes(), cpu=1, load_address=0x200,
                            entry_address=symbols['_udeks_program_entry'][0],
                            bss_size=symbols['__BSS_SIZE__'][0])
    (out/(name+'.BIN')).write_bytes(image)
    print('Independent', name+'.BIN:', len(image), 'bytes')


if __name__ == '__main__': main()

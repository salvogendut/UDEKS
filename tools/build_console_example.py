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
    args = parser.parse_args()
    name = args.name.upper()
    if not re.fullmatch(r'[A-Z0-9_-]{1,12}', name): parser.error('invalid command name')
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    def run(*command): subprocess.run(command, cwd=ROOT, check=True)
    run('cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Os',
        '-I', 'user/include', '-o', str(out/'program.s'), str(args.source.resolve()))
    objects = []
    for label, source in (('entry', 'user/lib/entry.s'), ('syscall', 'user/lib/syscall.s'),
                          ('program', out/'program.s')):
        obj = out/(label+'.o'); objects.append(str(obj))
        run('ca65', '--cpu', '6502', '-o', str(obj), str(source))
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

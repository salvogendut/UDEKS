#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the standalone raster suite on 1986 or VICE; keep complete pixel output."""
import argparse
import importlib
import hashlib
import json
import shlex
import subprocess
from pathlib import Path
from graphics_raster_audit import ROOT


def emulator_provenance(emulator, sources):
    headers = subprocess.check_output(['git', '-C', str(emulator), 'ls-files', '*.h'], text=True).splitlines()
    inputs = set(sources) | {emulator / name for name in headers} | {emulator / 'Makefile.am'}
    return {'revision': subprocess.check_output(['git', '-C', str(emulator), 'rev-parse', 'HEAD'], text=True).strip(),
            'tracked_changes': subprocess.check_output(['git', '-C', str(emulator), 'status', '--porcelain',
                                                        '--untracked-files=no'], text=True).splitlines(),
            'input_sha256': {str(path.relative_to(emulator)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in sorted(inputs)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=('1986', 'vice'), required=True)
    parser.add_argument('--work', type=Path, default=ROOT / 'build/graphics-raster-bench')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--emulator', type=Path, default=ROOT.parent / '1986')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.engine == '1986':
        sources = importlib.import_module('1986_input_smoke_build').emulator_sources(args.emulator)
        before = emulator_provenance(args.emulator, sources)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'sdl3'], text=True))
        runner = args.work / '1986-raster-bench'
        subprocess.run(['cc', '-std=gnu11', '-O2', '-I' + str(args.emulator / 'src'),
                        str(ROOT / 'tools/1986_raster_bench.c'), *map(str, sources),
                        *flags, '-lm', '-o', str(runner)], check=True)
    for variant in ('baseline', 'static-scratch'):
        for case in range(4):
            program = args.work / f'{variant}-{case}.prg'
            output = args.output / f'{args.engine}-{variant}-{case}.bin'
            if args.engine == '1986':
                command = [str(runner), str(program), str(output)]
            else:
                command = ['python3', str(ROOT / 'tools/vice_capture.py'), str(program), str(output),
                           '--entry', '0x2000', '--result-address', '0x7fc0', '--result-size', '8096',
                           '--state-offset', '5', '--raw-load', '--timeout', '90']
            print(f'{args.engine}: {variant}, workload {case}', flush=True)
            subprocess.run(command, check=True)
    if args.engine == '1986':
        after = emulator_provenance(args.emulator, sources)
        if before['revision'] != after['revision'] or before['input_sha256'] != after['input_sha256']:
            raise RuntimeError('emulator inputs changed during benchmark; rerun required')
        (args.output / '1986-provenance.json').write_text(json.dumps(before, indent=2) + '\n')


if __name__ == '__main__':
    main()

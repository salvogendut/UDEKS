#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay the resident link in isolation, with a candidate graphics object.

This image is deliberately NOT packaged or booted: all derived private import
bridges would need regeneration. Its purpose is whole-link budget measurement.
"""
import argparse
import json
import re
import shlex
import subprocess
from pathlib import Path
from graphics_raster_audit import ROOT


def link_command(output):
    joined = output.replace('\\\n', ' ')
    commands = [line for line in joined.splitlines()
                if line.startswith('cl65 ') and '-C cfg/8502-bootstrap.cfg' in line]
    if len(commands) != 1:
        raise ValueError('expected exactly one normal kernel link command')
    def flags(match):
        path = (ROOT / match[1]).resolve()
        if not path.is_relative_to(ROOT / 'build'):
            raise ValueError('force-import manifest outside build/')
        return path.read_text().strip()
    command = re.sub(r'\$\(cat ([^()\s]+)\)', flags, commands[0])
    if '$' in command:
        raise ValueError('unexpanded shell expression in link')
    return shlex.split(command)


def segments(text):
    block = text.split('Segment list:', 1)[1].split('Exports list', 1)[0]
    return {name: {'start': int(start, 16), 'end': int(end, 16), 'size': int(size, 16)}
            for name, start, end, size in re.findall(
                r'^(\w+)\s+([0-9A-F]{6})\s+([0-9A-F]{6})\s+([0-9A-F]{6})\s+', block, re.M)}


def reference_link_command(work):
    """Replay the pre-ASM link only in isolation; never edit installed outputs.

    Its baseline is the preserved C image, not the now-optimized OS. Remove
    only the two replacement objects and their measured placement padding.
    All split outputs still must be retargeted by the caller before linking.
    """
    command = link_command(subprocess.check_output(
        ['make', '-Bn', 'build/8502/udeks-8502.bin'], cwd=ROOT, text=True))
    extras = ['build/8502/vic_span.o', 'build/8502/vic_pixel.o']
    present = [item in command for item in extras]
    if any(present) and not all(present):
        raise ValueError('partial raster integration in production link')
    if all(present):
        for item in extras:
            command.remove(item)
        source = (ROOT / 'src/8502/vic_graphics.s').read_text()
        if 'build/8502/vic_clear.o' in command:
            command.remove('build/8502/vic_clear.o')
            source, shared_count = re.subn(r'raster_shared_placement_reserve:\n\s*\.res (?:294|136|59|280), \$ea',
                                          'raster_shared_placement_reserve:', source)
            if shared_count != 1:
                raise ValueError('shared padding changed; review reference reconstruction')
        source, count = re.subn(r'raster_primitives_placement_reserve:\n\s*\.res 173, \$ea',
                               'raster_primitives_placement_reserve:', source)
        if count != 1:
            raise ValueError('replacement padding changed; review reference reconstruction')
        path = work / 'reference-transport.s'
        path.write_text(source)
        subprocess.run(['ca65', '--cpu', '6502', '-I', str(ROOT / 'src/8502'),
                        '-o', str(path.with_suffix('.o')), str(path)], check=True)
        command[command.index('build/8502/vic_graphics_transport.o')] = str(path.with_suffix('.o'))
    return command


def reference_segments():
    return segments((ROOT / 'bench/artifacts/2026-09-28-graphics-span/sources/build/8502/udeks-8502.map').read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=ROOT / 'build/graphics-raster-link')
    parser.add_argument('--candidate', type=Path, default=ROOT / 'build/graphics-raster-audit/static-scratch.o')
    parser.add_argument('--baseline', type=Path, default=ROOT / 'build/graphics-raster-audit/baseline.o',
                        help='automatic-local reference object, even after scratch integration')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    base_command = reference_link_command(args.work)
    config = (ROOT / 'cfg/8502-bootstrap.cfg').read_text()
    # Retarget every split output, including task/common-RAM services. No
    # generated production provider is overwritten by this experimental link.
    config = re.sub(r'file = "(build/[^"\n]+)"',
                    lambda m: 'file = "' + str(args.work / Path(m[1]).name) + '"', config)
    cfg = args.work / 'experimental.cfg'
    cfg.write_text(config)
    report = {'qualification': 'link-budget only; experimental images must not be booted'}
    for label, candidate in (('baseline', args.baseline), ('static-scratch', args.candidate)):
        directory = args.work / label
        directory.mkdir(exist_ok=True)
        # Each link has its own split-output directory too.
        local_config = directory / 'kernel.cfg'
        local_config.write_text(config.replace(str(args.work) + '/', str(directory) + '/'))
        command = base_command[:]
        command[command.index('-C') + 1] = str(local_config)
        map_path = directory / 'kernel.map'
        command[command.index('-m') + 1] = str(map_path)
        command[command.index('-o') + 1] = str(directory / 'kernel.bin')
        if candidate:
            index = command.index('build/8502/vic_graphics.o')
            command[index] = str(candidate)
        subprocess.run(command, cwd=ROOT, check=True)
        report[label] = segments(map_path.read_text())
    report['linked_end_reduction'] = report['baseline']['BSS']['end'] - report['static-scratch']['BSS']['end']
    text = json.dumps(report, indent=2) + '\n'
    (args.work / 'report.json').write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()

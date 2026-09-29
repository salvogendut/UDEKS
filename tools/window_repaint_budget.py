#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure the private continuation object; no resident link/placement claim."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from gen_capability_imports import canonicalize
from graphics_span_bench import object_sizes

ROOT = Path(__file__).resolve().parents[1]


def measure(work):
    policy = work / 'policy.o'
    layout = (work / 'layout.bin').read_bytes()
    if len(layout) != 4:
        raise ValueError('incomplete target sizeof probe')
    dump = subprocess.check_output(['od65', '--dump-imports', str(policy)], text=True)
    (work / 'imports.txt').write_text(dump)
    (work / 'segments.txt').write_text(subprocess.check_output(
        ['od65', '--dump-segments', str(policy)], text=True))
    imports = canonicalize([(name, size.lower()) for size, name in re.findall(
        r'Address size:\s+0x([0-9A-Fa-f]+).*?Name:\s*"([^"]+)"', dump, re.S)])
    sizes = object_sizes(policy)
    if any(sizes.get(name, 0) for name in ('BSS', 'DATA', 'ZEROPAGE')):
        raise ValueError('policy acquired hidden mutable state')
    inputs = [ROOT / 'include/udeks/window_repaint.h', ROOT / 'src/services/window/repaint_policy.c',
              ROOT / 'bench/window-repaint-policy/layout.c', ROOT / 'cfg/8502-repaint-layout.cfg',
              ROOT / 'tools/window_repaint_budget.py', ROOT / 'mk/toolchain.mk', ROOT / 'Makefile',
              ROOT / 'tests/test_window_repaint_policy.py']
    report = {
        'scope': 'compile-only private policy; object CODE is a lower bound, not linked runtime closure',
        'sizes': sizes, 'cc65_layout': dict(zip(('job', 'ticket', 'work', 'window'), layout)),
        'imports': imports,
        'cc65': subprocess.check_output(['cc65', '--version'], stderr=subprocess.STDOUT, text=True).strip(),
        'input_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
        'output_sha256': {name: hashlib.sha256((work / name).read_bytes()).hexdigest()
                          for name in ('policy.o', 'policy.s', 'layout.o', 'layout.bin', 'imports.txt', 'segments.txt')},
    }
    (work / 'budget.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({name: report[name] for name in ('scope', 'sizes', 'cc65_layout')}, indent=2))


def preserve(work):
    report = json.loads((work / 'budget.json').read_text())
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    for name, expected in report['input_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('policy input drift: ' + name)
    for name, expected in report['output_sha256'].items():
        if sha(work / name) != expected:
            raise ValueError('policy output drift: ' + name)
    name = '2026-09-29-repaint-policy'
    artifact, result = ROOT / 'bench/artifacts' / name, ROOT / 'bench/results' / name
    if artifact.exists() or result.exists():
        raise ValueError('refusing to overwrite policy measurement')
    for name in report['input_sha256']:
        target = artifact / 'inputs' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    (artifact / 'build').mkdir()
    for name in report['output_sha256']:
        shutil.copy2(work / name, artifact / 'build' / name)
    result.mkdir(parents=True)
    shutil.copy2(work / 'budget.json', result / 'budget.json')
    for directory in (artifact, result):
        files = sorted(path for path in directory.rglob('*') if path.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(
            f'{sha(path)}  {path.relative_to(directory)}\n' for path in files))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path)
    parser.add_argument('--preserve', action='store_true')
    args = parser.parse_args()
    measure(args.work)
    if args.preserve:
        preserve(args.work)

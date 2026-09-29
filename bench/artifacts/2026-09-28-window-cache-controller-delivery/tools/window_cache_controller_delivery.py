#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold-boot/lifetime proof for the WHOLE C controller, without GUI invocation."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
import graphics_cache_delivery as base
BASE_VERIFY = base.verify

ROOT = base.ROOT
WORK = ROOT / 'build/window-cache-controller-delivery'
NAME = '2026-09-28-window-cache-controller-delivery'
PROOF = ROOT / 'bench/artifacts/2026-09-28-window-cache-controller'
CORE = 0x4200
HEADER = 0x5210
SCHEDULER = 0x6000
SLOT_BYTES = 0x1020
LABELS = {'boot', 'xinit', 'clock', 'wave', 'complete', 'utilities', 'shutdown', 'restart'}

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def fixture(module):
    if not module or len(module) > HEADER-CORE:
        raise ValueError('controller is empty or reaches identity')
    identity = (b'VCC2\x00\x01' + CORE.to_bytes(2, 'little') + len(module).to_bytes(2, 'little') +
        (sum(module) & 65535).to_bytes(2, 'little') + (0x42d5).to_bytes(2, 'little') +
        (2224).to_bytes(2, 'little'))
    return module.ljust(HEADER-CORE, b'\0') + identity

def envelope(scheduler, module):
    # Reuse the canonical parser/checksum checks, NOT its small-core envelope.
    base.envelope(scheduler, b'\xea')
    if SCHEDULER+len(scheduler)-2 > 0x7fc0:
        raise ValueError('scheduler source reaches sprite memory')
    return CORE.to_bytes(2, 'little') + fixture(module).ljust(SCHEDULER-CORE, b'\0') + scheduler[2:]

def relocated_constants(text):
    fields = dict(re.findall(r'^(\w+)\s*=\s*\$([0-9a-f]+)$', text, re.M))
    move = ('SCHEDULER_OVERLAY_LOAD', 'SCHEDULER_OVERLAY_END', 'SCHEDULER_OVERLAY_PAGE_SOURCE',
        'SCHEDULER_OVERLAY_TAIL_SOURCE', 'TASK_ACTIVATION_CONTEXT_SOURCE', 'TASK_ACTIVATION_TAIL_SOURCE')
    if any(n not in fields for n in move) or int(fields[move[0]], 16) != 0x5000:
        raise ValueError('scheduler source constants changed')
    for n in move:
        old = int(fields[n], 16)
        text, count = re.subn(r'^'+n+r'\s*=\s*\$[0-9a-f]+$', f'{n} = ${old+0x1000:04x}', text, flags=re.M)
        if count != 1: raise ValueError('ambiguous source '+n)
    return text

def validate_slot(slot, module):
    if len(slot) != SLOT_BYTES or slot != fixture(module):
        raise ValueError('delivered full controller/identity/padding changed')
    return {'bytes': len(module), 'slot_sha256': hashlib.sha256(slot).hexdigest(),
        'core_sha256': hashlib.sha256(slot[:len(module)]).hexdigest()}

def build():
    from gen_boot_console_imports import write_constants
    WORK.mkdir(parents=True, exist_ok=True)
    for line in (PROOF / 'SHA256SUMS').read_text().splitlines():
        sha, name = line.split('  ', 1)
        if digest(PROOF / name) != sha: raise ValueError('qualified controller drift '+name)
    module = (PROOF / 'build/module.bin').read_bytes()
    canonical = ROOT / 'build/boot/scheduler-overlay.prg'
    payload = envelope(canonical.read_bytes(), module)
    (WORK / 'secondary.prg').write_bytes(payload)
    (WORK / 'core.bin').write_bytes(module)
    (WORK / 'scheduler-overlay-delivery.inc').write_text(relocated_constants(
        (ROOT / 'build/8502/scheduler-overlay-delivery.inc').read_text()))
    for name, cfg in (('scheduler-tail-installer', '8502-scheduler-tail-installer'),
                      ('task-switch-activation', '8502-task-switch-activation')):
        subprocess.run(['ca65', '--cpu', '6502', '-I', str(WORK), '-o', str(WORK / (name+'.o')),
            str(ROOT / 'src/boot' / (name+'.s'))], check=True)
        subprocess.run(['ld65', '-C', str(ROOT / 'cfg' / (cfg+'.cfg')), '-m', str(WORK / (name+'.map')),
            '-o', str(WORK / (name+'.bin')), str(WORK / (name+'.o'))], check=True)
    write_constants(*[str(ROOT / 'build/boot' / n) for n in ('8502-boot-console.bin',
        '8502-boot-delivery.bin', '8502-capability.bin', 'capability-installer.bin')],
        str(WORK / 'task-switch-activation.bin'), str(ROOT / 'build/8502/udeks-8502.map'),
        str(ROOT / 'build/8502/udeks-8502-panic-probe.map'), str(WORK / 'boot-console-delivery.inc'))
    subprocess.run(['ca65', '--cpu', '6502', '-I', str(WORK), '-o', str(WORK / 'boot-console-installer.o'),
        str(ROOT / 'src/boot/boot-console-installer.s')], check=True)
    subprocess.run(['ld65', '-C', str(ROOT / 'cfg/8502-boot-console-installer.cfg'),
        '-o', str(WORK / 'boot-console-installer.bin'), str(WORK / 'boot-console-installer.o')], check=True)
    source = (ROOT / 'src/boot/stage1.s').read_text()
    for old, new in (('ldx #<SCHEDULER_OVERLAY_LOAD', 'ldx #<$4200'),
                     ('ldy #>SCHEDULER_OVERLAY_LOAD', 'ldy #>$4200')):
        if source.count(old) != 1: raise ValueError('secondary LOAD seam changed')
        source = source.replace(old, new)
    (WORK / 'stage1.s').write_text(source)
    subprocess.run(['ca65', '--cpu', '6502', '-I', str(WORK), '-o', str(WORK / 'stage1.o'),
        str(WORK / 'stage1.s')], check=True)
    subprocess.run(['ld65', '-C', str(ROOT / 'cfg/8502-stage1.cfg'), '-m', str(WORK / 'stage1.map'),
        '-o', str(WORK / 'stage1.bin'), str(WORK / 'stage1.o')], check=True)
    # Every altered byte must be one of the relocation operands/checksums.
    differences = {}
    expected = {'stage1': [(0x50, 0x42), (0x62, 0x72)],
        'scheduler-tail-installer': [(0x50,0x60), (0x50,0x60), (0x54,0x64)],
        'task-switch-activation': [(0x60,0x70), (0x61,0x71)]}
    for n, changes in expected.items():
        old = (ROOT / 'build/boot' / (n+'.bin')).read_bytes(); new = (WORK / (n+'.bin')).read_bytes()
        diff = [(i,a,b) for i,(a,b) in enumerate(zip(old,new)) if a!=b]
        if len(old) != len(new) or [(a,b) for i,a,b in diff] != changes:
            raise ValueError('unexpected relocation byte delta '+n+': '+repr(diff))
        differences[n] = diff
    old = (ROOT / 'build/boot/boot-console-installer.bin').read_bytes()
    new = (WORK / 'boot-console-installer.bin').read_bytes()
    def console_checksum(path):
        return int(re.search(r'BOOT_CONSOLE_IMAGE_CHECKSUM = \$([0-9a-f]+)', path.read_text())[1], 16)
    before_sum = console_checksum(ROOT / 'build/8502/boot-console-delivery.inc')
    after_sum = console_checksum(WORK / 'boot-console-delivery.inc')
    expected_console = bytearray(old)
    for shift in (0, 8):
        pattern = bytes((0xc9, (before_sum >> shift) & 255, 0xd0))
        if old.count(pattern) != 1: raise ValueError('ambiguous console checksum operand')
        expected_console[old.index(pattern)+1] = (after_sum >> shift) & 255
    if bytes(expected_console) != new: raise ValueError('console installer changed beyond checksum operands')
    differences['boot-console-installer'] = [(i,a,b) for i,(a,b) in enumerate(zip(old,new)) if a!=b]
    command = base.disk_command(subprocess.check_output(['make', '-Bn', 'build/boot/udeks.d71'], cwd=ROOT, text=True))
    for flag, file in (('--stage1','stage1.bin'), ('--scheduler-overlay','secondary.prg'),
        ('--scheduler-tail-installer','scheduler-tail-installer.bin'),
        ('--task-switch-activation','task-switch-activation.bin'),
        ('--boot-console-installer','boot-console-installer.bin'), ('--d64-output','delivery.d64')):
        command[command.index(flag)+1] = str(WORK / file)
    command[-1] = str(WORK / 'delivery.d71')
    subprocess.run(command, cwd=ROOT, check=True)
    paths = [Path(__file__), ROOT / 'tools/graphics_cache_delivery.py',
        ROOT / 'tools/gen_boot_console_imports.py', ROOT / 'tools/build_scheduler_overlay.py',
        ROOT / 'tools/shadow_boot_probe.py', ROOT / 'tools/capability_relocation_probe.py',
        ROOT / 'tools/vice_capture.py', ROOT / 'tools/1986_input_smoke_build.py',
        ROOT / 'tools/1986_input_smoke.c', ROOT / 'tools/graphics_raster_bench_run.py',
        ROOT / 'tools/bench_decode.py', ROOT / 'Makefile',
        ROOT / 'build/8502/scheduler-overlay-delivery.inc',
        ROOT / 'build/8502/boot-console-delivery.inc',
        ROOT / 'build/8502/udeks-8502.map', ROOT / 'build/8502/udeks-8502-panic-probe.map',
        PROOF / 'build/module.bin', PROOF / 'build/build-report.json']
    paths += [ROOT / 'src/boot' / (n+'.s') for n in (*expected, 'boot-console-installer')]
    paths += [ROOT / 'cfg' / n for n in ('8502-stage1.cfg', '8502-scheduler-tail-installer.cfg',
        '8502-task-switch-activation.cfg', '8502-boot-console-installer.cfg')]
    paths += [ROOT / 'tests/test_window_cache_controller_delivery.py']
    paths += [ROOT / 'build/boot' / (n+'.bin') for n in (*expected, 'boot-console-installer')]
    for arg in command:
        p = Path(arg)
        if p.is_file() and p.resolve().is_relative_to(ROOT) and not p.resolve().is_relative_to(WORK):
            paths.append(p.resolve())
    linked = ['core.bin','secondary.prg','stage1.s','stage1.bin','stage1.map',
        'scheduler-overlay-delivery.inc','boot-console-delivery.inc','boot-console-installer.bin',
        'scheduler-tail-installer.bin','scheduler-tail-installer.map','task-switch-activation.bin',
        'task-switch-activation.map']
    report = {'qualification': 'whole-controller cold-boot delivery only; uninvoked; GUI moves disabled',
        'scheduler_source': SCHEDULER, 'secondary_load': CORE, 'secondary_end': CORE+len(payload)-2,
        'module_bytes': len(module), 'slot_bytes': SLOT_BYTES, 'identity': HEADER,
        'resident_delivery_bytes_added': 0, 'relocation_deltas': differences, 'disk_recipe': command,
        'core_sha256': digest(WORK / 'core.bin'),
        'disk_sha256': {n:digest(WORK / n) for n in ('delivery.d71','delivery.d64')},
        'normal_disks_before': {n:digest(ROOT / 'build/boot' / n) for n in ('udeks.d71','udeks.d64')},
        'inputs_sha256': {str(p.relative_to(ROOT)):digest(p) for p in sorted(set(paths))},
        'linked_sha256': {n:digest(WORK / n) for n in linked}}
    (WORK / 'build-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('inputs_sha256','linked_sha256','disk_recipe')}, indent=2))

def verify(report):
    BASE_VERIFY(report)
    for n, sha in report['linked_sha256'].items():
        if digest(WORK / n) != sha: raise ValueError('linked artifact drift '+n)

def configure():
    # Reuse the mature read-only smoke paths, with explicit new slot sizing.
    base.WORK = WORK; base.CORE_BYTES = SLOT_BYTES
    base.validate_slot = validate_slot; base.verify = verify

def bind_run(engine):
    report = json.loads((WORK / 'build-report.json').read_text()); verify(report)
    patterns = ('vice-*.bin', 'vice-results.json', 'vice-provenance.txt') if engine == 'vice' else (
        '1986-*-core.bin', '1986-*.log', '1986-results.json', '1986-provenance.json')
    paths = sorted({p for pattern in patterns for p in WORK.glob(pattern)})
    expected = 18 if engine == 'vice' else 6
    if len(paths) != expected: raise ValueError('incomplete run outputs')
    (WORK / f'{engine}-binding.json').write_text(json.dumps({
        'build_report_sha256': digest(WORK / 'build-report.json'),
        'disk_sha256': report['disk_sha256'], 'raw_sha256': {p.name:digest(p) for p in paths}}, indent=2)+'\n')

def preserve():
    report = json.loads((WORK / 'build-report.json').read_text()); verify(report)
    module = (WORK / 'core.bin').read_bytes()
    vice = json.loads((WORK / 'vice-results.json').read_text())
    native = json.loads((WORK / '1986-results.json').read_text())
    for engine in ('vice', '1986'):
        binding = json.loads((WORK / f'{engine}-binding.json').read_text())
        if binding['build_report_sha256'] != digest(WORK / 'build-report.json') or binding['disk_sha256'] != report['disk_sha256']:
            raise ValueError('run/build binding drift')
        for n, sha in binding['raw_sha256'].items():
            if digest(WORK / n) != sha: raise ValueError('bound raw drift '+n)
    if set(vice) != {'d71','d64'} or set(native) != {'d71','d64'}: raise ValueError('missing format')
    for fmt in ('d71','d64'):
        if set(vice[fmt]) != LABELS: raise ValueError('incomplete VICE lifetime gate')
        for label in LABELS:
            slot = (WORK / f'vice-{fmt}-{label}-core.bin').read_bytes()
            if slot[:2] != CORE.to_bytes(2,'little') or validate_slot(slot[2:],module) != vice[fmt][label]:
                raise ValueError('VICE capture drift')
        if validate_slot((WORK / f'1986-{fmt}-core.bin').read_bytes(),module) != native[fmt]:
            raise ValueError('native capture drift')
        log = (WORK / f'1986-{fmt}.log').read_text()
        if 'PASS: repeated native wave drags and console cancellation' not in log or sum(
                line.startswith('stress ') for line in log.splitlines()) != 32:
            raise ValueError('native drag/input gate missing')
    artifacts = ROOT / 'bench/artifacts' / NAME; results = ROOT / 'bench/results' / NAME
    if artifacts.exists() or results.exists(): raise ValueError('refusing to overwrite evidence')
    artifacts.mkdir(parents=True); results.mkdir(parents=True)
    for n in report['inputs_sha256']:
        dest = artifacts / n; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT / n,dest)
    for n in set(report['linked_sha256']) | set(report['disk_sha256']) | {'build-report.json'}:
        dest = artifacts / 'build' / n; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(WORK / n,dest)
    for pattern in ('vice-*.bin','1986-*-core.bin','1986-*.log','*-results.json','*-provenance.*','*-binding.json'):
        for p in WORK.glob(pattern): shutil.copy2(p,results / p.name)
    for directory in (artifacts,results):
        paths = sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('build','vice','1986','preserve'))
    a = p.parse_args()
    if a.action == 'build': build()
    else:
        configure()
        if a.action == 'vice': base.probe_vice(); bind_run('vice')
        elif a.action == '1986': base.probe_1986(); bind_run('1986')
        else: preserve()

if __name__ == '__main__': main()

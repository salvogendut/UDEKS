#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated bank-1 repaint closure/transport proof, never packages an OS disk."""
import argparse
import hashlib
import importlib
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/bench/window-repaint-bank'
SOURCE = ROOT / 'bench/window-repaint-bank'
OLD = ROOT / 'bench/window-cache-c-runtime'
NAME = '2026-09-29-repaint-bank'
CASES = ('normal', 'zp-leak', 'irq-leak', 'shell-stack')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('diagnostic template changed: ' + old[:60])
    return text.replace(old, new)


def diagnostic_driver(text):
    """Reuse the tested oracle, not its obsolete module placement/row operations."""
    text = replace_once(text, 'lda #<$4200', 'lda #<$d100')
    text = replace_once(text, 'lda #>$4200', 'lda #>$d100')
    text = replace_once(text, 'ldx #$0b                ; exact private $4200-$4CFF envelope',
                        'ldx #$0f                ; isolated $D100-$DFFF envelope')
    start, end = text.index('\nseed:\n') + 1, text.index('\nseed_end:\n') + 1
    text = text[:start] + '''seed:
        lda #$00
        sta WORKER
        ldx #$00
        lda #$a5
seed_stack:
        sta STACK_BOTTOM,x
        inx
        cpx #$f0
        bcc seed_stack
        lda #$5a
        ldx #$0f
guard_stack:
        sta STACK_TOP,x
        dex
        bpl guard_stack
        ldx #$15
guard_stack_low:
        sta $523a,x
        dex
        bpl guard_stack_low
        ldx #$0d
guard_state:
        sta $dff2,x
        dex
        bpl guard_state
        ldx #$19
guard_cache_state:
        sta $5220,x
        dex
        bpl guard_cache_state
        lda #<$d000
        sta ptr2
        lda #>$d000
        sta ptr2+1
        ldy #$00
guard_bootfs:
        tya
        eor #$69
        sta (ptr2),y
        iny
        bne guard_bootfs
        lda #<$5350
        sta ptr2
        lda #>$5350
        sta ptr2+1
        ldx #$09
        ldy #$00
seed_cache:
        tya
        eor #$69
        sta (ptr2),y
        iny
        bne seed_cache
        inc ptr2+1
        dex
        bne seed_cache
        lda #<$e700
        sta ptr2
        lda #>$e700
        sta ptr2+1
        ldx #$09
        ldy #$00
seed_ush:
        tya
        eor #$69
        sta (ptr2),y
        iny
        bne seed_ush
        inc ptr2+1
        dex
        bne seed_ush
        lda #$00
        sta KERNEL
        rts
''' + text[end:]
    # The first 9-page cache loop ends at $5C4F: it deliberately includes the
    # first 80 bytes of the adjacent screen matrix in this standalone guard.
    start, end = text.index('\nscan:\n') + 1, text.index('\nmeasure_water:\n') + 1
    text = text[:start] + '''scan:
        lda #$00
        sta WORKER
        ldx #$00
scan_low:
        lda STACK_BOTTOM,x
        cmp #$a5
        bne guard_bad
        inx
        cpx #$40
        bcc scan_low
        ldx #$0f
scan_stack_guards:
        lda STACK_TOP,x
        cmp #$5a
        bne guard_bad
        dex
        bpl scan_stack_guards
        ldx #$15
scan_stack_low_guard:
        lda $523a,x
        cmp #$5a
        bne guard_bad
        dex
        bpl scan_stack_low_guard
        ldx #$0d
scan_state:
        lda $dff2,x
        cmp #$5a
        bne guard_bad
        dex
        bpl scan_state
        ldx #$19
scan_cache_state:
        lda $5220,x
        cmp #$5a
        bne guard_bad
        dex
        bpl scan_cache_state
        ldy #$00
scan_bootfs:
        tya
        eor #$69
        cmp $d000,y
        bne guard_bad
        iny
        bne scan_bootfs
        lda #<$5350
        sta ptr2
        lda #>$5350
        sta ptr2+1
        ldx #$09
        ldy #$00
scan_cache:
        tya
        eor #$69
        cmp (ptr2),y
        bne guard_bad
        iny
        bne scan_cache
        inc ptr2+1
        dex
        bne scan_cache
        beq measure_water       ; X reached zero; copied code uses relative flow
guard_bad:
        inc $f78a
''' + text[end:]
    text = replace_once(text, 'RUN+scan_end-scan < $f740', 'RUN+scan_end-scan < $f780')
    text = replace_once(text, 'seed_end-seed < $80', 'seed_end-seed < $100')
    text = replace_once(text, '''ldx #seed_end-seed-1
install_seed:
        lda seed,x
        sta RUN,x
        dex
        bpl install_seed''', '''ldx #$00
install_seed:
        lda seed,x
        sta RUN,x
        inx
        cpx #seed_end-seed
        bcc install_seed''')
    text = replace_once(text, '''ldx #scan_end-scan-1
install_scan:
        lda scan,x
        sta RUN,x
        dex
        bpl install_scan''', '''ldx #$00
install_scan:
        lda scan,x
        sta RUN,x
        inx
        cpx #scan_end-scan
        bcc install_scan''')
    # The scan is only called AFTER stopping the diagnostic IRQ. Its extended
    # copied image can then reuse those retired bytes, never while IRQ is live.
    text = replace_once(text, 'build/bench/window-cache-c-runtime/module-envelope.bin',
                        'build/bench/window-repaint-bank/module-envelope.bin')
    text = replace_once(text, 'module_image_end-module_image = $b00',
                        'module_image_end-module_image = $f00')
    text += '\n        .segment "CODE"\n_vic_cache_row_candidate: rts\n'
    text = replace_once(text, '.import _private_cache_policy_call, _vic_cache_row_candidate',
                        '.import _private_cache_policy_call')
    return text


def verify_layout(segments, module_bytes):
    s = {name: (start, end) for name, start, end in segments}
    if set(s) != {'ZEROPAGE', 'ENTRY', 'CODE', 'HIGHBSS'}:
        raise ValueError('unbudgeted segment')
    if s['ZEROPAGE'] != (6, 31) or s['ENTRY'] != (0xD100, 0xD102):
        raise ValueError('runtime or fixed entry moved')
    if s['HIGHBSS'] != (0xDFE0, 0xDFF1):
        raise ValueError('bank-owned state moved')
    if s['CODE'][0] != 0xD103 or s['CODE'][1] >= 0xDFE0:
        raise ValueError('code overlaps state/guard')
    if module_bytes != s['CODE'][1] - 0xD100 + 1:
        raise ValueError('emitted image/map mismatch')
    return s


def verify_ownership(memory, cache):
    """Lock the neighboring reservations, not an inference from an old map."""
    expected = {'UDEKS_BOOTFS_BASE':0xA000, 'UDEKS_BOOTFS_LIMIT':0xD100,
                'UDEKS_COMMON_BASE':0xF000, 'UDEKS_C_STACK_BOTTOM':0xE700,
                'UDEKS_C_STACK_TOP':0xEFF0}
    for name, value in expected.items():
        m = re.search(r'^#define\s+'+name+r'\s+0x([0-9a-f]+)u\s*$',memory,re.M|re.I)
        if m is None or int(m[1],16) != value:
            raise ValueError('neighbor reservation changed: '+name)
    if not re.search(r'^STACK_TOP\s*=\s*STACK_BOTTOM\+\$f0\s*$',cache,re.M|re.I):
        raise ValueError('cache private stack size changed')
    for name, value in {'STACK_BOTTOM':0x5250,
                        'CACHE':0x5350, 'CACHE_LIMIT':0x5C00, 'LEASE':0x5220}.items():
        m = re.search(r'^'+name+r'\s*=\s*\$([0-9a-f]+)\s*$',cache,re.M|re.I)
        if m is None or int(m[1],16) != value:
            raise ValueError('cache ownership changed: '+name)


def build():
    from placement_audit import parse_map
    from graphics_span_bench import object_sizes
    WORK.mkdir(parents=True, exist_ok=True)
    verify_ownership((ROOT / 'include/udeks/memory.h').read_text(),
                     (ROOT / 'src/services/window/cache/layout.inc').read_text())
    for name, path in (('lane', ROOT / 'src/services/window/repaint_lane.c'),
                       ('dispatch', SOURCE / 'dispatch.c')):
        subprocess.run(['cl65', '-t', 'none', '--cpu', '6502', '-Oirs', '--standard', 'c99',
                        '-I', str(ROOT / 'include'), '-c', '-o', str(WORK / (name+'.o')),
                        str(path)], check=True)
    for name in ('module', 'gateway'):
        subprocess.run(['ca65', '-I', str(SOURCE), '-o', str(WORK / (name+'.o')),
                        str(SOURCE / (name+'.s'))], check=True)
    subprocess.run(['ld65', '-C', str(OLD / 'gateway.cfg'), '-o', str(WORK / 'gateway.bin'),
                    str(WORK / 'gateway.o')], check=True)
    subprocess.run(['cl65', '-t', 'none', '-C', str(SOURCE / 'module.cfg'),
                    '-m', str(WORK / 'module.map'), '-o', str(WORK / 'module.bin'),
                    *[str(WORK / (n+'.o')) for n in ('module', 'dispatch', 'lane')]], check=True)
    module = (WORK / 'module.bin').read_bytes()
    objects, segments = parse_map((WORK / 'module.map').read_text())
    verify_layout(segments, len(module))
    (WORK / 'module-envelope.bin').write_bytes(module.ljust(0xF00, b'\0'))
    # Self-contained link: no resident imports, no duplicated bank-0 helpers
    # reached while worker FLAT is selected. Archive the EXACT runtime library.
    libraries = {Path(n.split('(', 1)[0]) for n in objects if 'none.lib(' in n}
    if len(libraries) != 1:
        raise ValueError('missing/ambiguous linked runtime library')
    library = libraries.pop()
    shutil.copy2(library, WORK / 'none.lib')
    subprocess.run(['cc', '-std=c99', '-O2', '-fpack-struct=1', '-Wno-unknown-pragmas',
                    '-DREPAINT_HOST', '-I'+str(ROOT / 'include'), '-I'+str(SOURCE),
                    str(SOURCE / 'probe.c'), str(SOURCE / 'dispatch.c'),
                    str(ROOT / 'src/services/window/repaint_lane.c'), '-o', str(WORK / 'oracle')], check=True)
    calls, trace, failure = map(int, subprocess.check_output([str(WORK / 'oracle')], text=True).split())
    if failure or calls < 100:
        raise ValueError('host command oracle failed/incomplete')
    (WORK / 'expected.h').write_text(f'#define EXPECTED_CALLS {calls}u\n#define EXPECTED_TRACE {trace}u\n')
    (WORK / 'driver.s').write_text(diagnostic_driver((OLD / 'driver.s').read_text()))
    launcher = (ROOT / 'bench/graphics-raster/launcher.s').read_text()
    launcher = replace_once(launcher, 'lda #<$7800', 'lda #<$eff0')
    launcher = replace_once(launcher, 'lda #>$7800', 'lda #>$eff0')
    (WORK / 'launcher.s').write_text(launcher)
    for name, path in (('binding', SOURCE / 'binding.s'), ('driver', WORK / 'driver.s'),
                       ('launcher', WORK / 'launcher.s')):
        subprocess.run(['ca65', '-I', str(SOURCE), '-o', str(WORK / (name+'.o')), str(path)], check=True)
    subprocess.run(['cc65', '-t', 'none', '--standard', 'c99', '-Oirs', '-I', str(WORK),
                    '-I', str(ROOT / 'include'), '-o', str(WORK / 'probe.s'),
                    str(SOURCE / 'probe.c')], check=True)
    subprocess.run(['ca65', '-o', str(WORK / 'probe.o'), str(WORK / 'probe.s')], check=True)
    subprocess.run(['cl65', '-t', 'none', '-C', str(OLD / 'probe.cfg'),
                    '-m', str(WORK / 'probe.map'), '-o', str(WORK / 'probe.bin'),
                    *[str(WORK / (n+'.o')) for n in ('launcher', 'probe', 'driver', 'binding')]], check=True)
    program = b'\x00\x20' + (WORK / 'probe.bin').read_bytes()
    (WORK / 'probe-normal.prg').write_bytes(program)
    gate = (WORK / 'gateway.bin').read_bytes()
    if program.count(gate) != 1:
        raise ValueError('ambiguous copied gateway')
    controls = {}
    for name, pattern, delta, byte in (
            ('zp-leak', b'\x68\x95\x06\xe8', 2, 7),
            ('irq-leak', b'\x08\x78\xd8', 1, 0x58),
            ('shell-stack', b'\xa9\x53\x85\x07', 1, 0xEF)):
        if gate.count(pattern) != 1:
            raise ValueError('ambiguous negative control '+name)
        offset = program.index(gate) + gate.index(pattern) + delta
        bad = bytearray(program); old = bad[offset]; bad[offset] = byte
        (WORK / f'probe-{name}.prg').write_bytes(bad)
        controls[name] = {'offset': offset, 'before': old, 'after': byte}
    inputs = list(SOURCE.iterdir()) + [Path(__file__), OLD / 'driver.s', OLD / 'probe.cfg',
        OLD / 'gateway.cfg', ROOT / 'src/services/window/repaint_lane.c',
        ROOT / 'include/udeks/repaint_lane.h', ROOT / 'include/udeks/window_repaint.h',
        ROOT / 'include/udeks/memory.h', ROOT / 'bench/graphics-raster/launcher.s',
        ROOT / 'src/services/window/cache/layout.inc',
        ROOT / 'cfg/8502-window-cache.cfg', ROOT / 'src/8502/vic_graphics.s',
        ROOT / 'src/boot/stage1-gateway.s',
        ROOT / 'tools/1986_raster_bench.c', ROOT / 'tools/1986_input_smoke_build.py',
        ROOT / 'tools/graphics_raster_bench_run.py', ROOT / 'tools/vice_capture.py',
        ROOT / 'tools/placement_audit.py', ROOT / 'tools/graphics_span_bench.py']
    outputs = [p for p in WORK.iterdir() if p.suffix in ('.bin', '.map', '.s', '.prg', '.lib', '.h', '.o')]
    report = {'scope': 'standalone placement/runtime proof; not cold-boot delivery, poll integration, NMI or hardware qualification',
        'module_bytes': len(module), 'state_bytes': 18, 'packet_bytes': 82,
        'gateway_bytes': len(gate), 'binding_bytes': object_sizes(WORK / 'binding.o')['CODE'],
        'segments': {n: [s,e] for n,s,e in segments},
        'code_spare': 0xDFE0 - (0xD100 + len(module)),
        'helpers': sorted(n.split('(',1)[1].rstrip('):') for n in objects if 'none.lib(' in n),
        'expected': {'calls': calls, 'trace': trace}, 'negative_controls': controls,
        'private_stack': [0x5250, 0x533F], 'state_guard': [0xDFF2, 0xDFFF],
        'cc65': subprocess.check_output(['cc65','--version'], stderr=subprocess.STDOUT, text=True).strip(),
        'input_sha256': {str(p.relative_to(ROOT)): digest(p) for p in sorted(inputs)},
        'output_sha256': {p.name: digest(p) for p in sorted(outputs)}}
    (WORK / 'build-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('input_sha256','output_sha256','helpers')}, indent=2))


def verify(report):
    for n, sha in report['input_sha256'].items():
        if digest(ROOT / n) != sha: raise ValueError('source drift '+n)
    for n, sha in report['output_sha256'].items():
        if digest(WORK / n) != sha: raise ValueError('build drift '+n)


def decode(data, expected, case='normal'):
    if len(data) != 8096 or data[:8] != b'RBNK\x01\x02\x00\x00':
        raise ValueError('incomplete/failed banked lane record')
    if int.from_bytes(data[8:10], 'little') != expected['calls'] or int.from_bytes(data[10:12], 'little') != expected['trace']:
        raise ValueError('command stream diverged from host oracle')
    irq = int.from_bytes(data[12:16], 'little')
    if not irq or data[24] != 15 or any(data[25:]):
        raise ValueError('missing IRQ/flag coverage or nonzero reserved bytes')
    failures = {'zp-leak': (17,), 'irq-leak': (16,), 'shell-stack': (20,22)}
    wanted = failures.get(case, ())
    if case not in CASES or any(data[i] != int(i in wanted) for i in range(16,23)):
        raise ValueError('runtime preservation/negative control mismatch')
    if case == 'shell-stack':
        if data[23] != 0xF0: raise ValueError('shell-stack fault did not bypass private stack')
    elif not 0x40 <= data[23] < 0xF0:
        raise ValueError('private stack unexercised or minimum guard violated')
    return {'calls': expected['calls'], 'trace': expected['trace'], 'interrupts': irq,
            'lowest_changed_stack_offset': data[23], 'detected_fields': list(wanted)}


def run(engine, output, emulator):
    from graphics_raster_bench_run import emulator_provenance
    report = json.loads((WORK / 'build-report.json').read_text()); verify(report)
    output.mkdir(parents=True, exist_ok=True)
    if engine == '1986':
        sources = importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
        provenance = emulator_provenance(emulator, sources)
        flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'], text=True))
        runner = WORK / '1986-repaint-bank'
        runner_source = (ROOT / 'tools/1986_raster_bench.c').read_text()
        runner_source = replace_once(runner_source, 'return 1;\n    }\n    FILE *output', '''
        fprintf(stderr, "packet op=%u result=%u epoch=%u phase=%u cursor=%u sp=%02X%02X map=%02X\\n",
            machine->mem.ram[0xf780], machine->mem.ram[0xf783],
            machine->mem.ram[0xf7cc] | (machine->mem.ram[0xf7cd]<<8),
            machine->mem.ram[0xf7d0],
            machine->mem.ram[0xf7ce] | (machine->mem.ram[0xf7cf]<<8),
            machine->mem.ram[7], machine->mem.ram[6], c128_mem_read(machine,0xff00));
        return 1;
    }
    FILE *output''')
        (WORK / 'runner.c').write_text(runner_source)
        subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator / 'src'),
            str(WORK / 'runner.c'), *map(str,sources), *flags, '-lm','-o',str(runner)], check=True)
    else:
        provenance = subprocess.check_output(['flatpak','info','net.sf.VICE'], text=True)
    decoded = {}; raw = {}
    for case in CASES:
        program = WORK / f'probe-{case}.prg'; path = output / f'{engine}-{case}.bin'
        cmd = ([str(runner),str(program),str(path),'RBNK'] if engine == '1986' else
            ['python3',str(ROOT / 'tools/vice_capture.py'),str(program),str(path),
             '--entry','0x2000','--raw-load','--result-address','0x7fc0','--result-size','8096',
             '--state-offset','5','--timeout','90'])
        subprocess.run(cmd, check=True)
        decoded[case] = decode(path.read_bytes(), report['expected'], case)
        raw[path.name] = digest(path); print(json.dumps({case:decoded[case]}), flush=True)
    verify(report)
    if engine == '1986' and emulator_provenance(emulator,sources) != provenance:
        raise ValueError('emulator source drift')
    (output / f'{engine}-run.json').write_text(json.dumps({'decoded':decoded,
        'raw_sha256':raw, 'build_report_sha256':digest(WORK / 'build-report.json'),
        'provenance':provenance}, indent=2)+'\n')


def preserve(output):
    report = json.loads((WORK / 'build-report.json').read_text()); verify(report)
    for engine in ('1986','vice'):
        r = json.loads((output / f'{engine}-run.json').read_text())
        if r['build_report_sha256'] != digest(WORK / 'build-report.json'):
            raise ValueError('run belongs to another build')
        if set(r['raw_sha256']) != {f'{engine}-{c}.bin' for c in CASES}:
            raise ValueError('incomplete positive/negative runs')
        for n, sha in r['raw_sha256'].items():
            if digest(output / n) != sha: raise ValueError('record drift '+n)
        for c in CASES:
            if decode((output / f'{engine}-{c}.bin').read_bytes(), report['expected'], c) != r['decoded'][c]:
                raise ValueError('decode drift')
    art = ROOT / 'bench/artifacts' / NAME; result = ROOT / 'bench/results' / NAME
    if art.exists() or result.exists(): raise ValueError('refusing to overwrite evidence')
    art.mkdir(parents=True); result.mkdir(parents=True)
    for n in report['input_sha256']:
        dest = art / 'inputs' / n; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT / n,dest)
    for n in set(report['output_sha256']) | {'build-report.json'}:
        dest = art / 'build' / n; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(WORK / n,dest)
    for engine in ('1986','vice'):
        for n in [f'{engine}-run.json'] + [f'{engine}-{c}.bin' for c in CASES]:
            shutil.copy2(output / n, result / n)
    for directory in (art, result):
        paths = sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('build','run','preserve'))
    p.add_argument('--engine', choices=('1986','vice'))
    p.add_argument('--emulator-root', type=Path, default=Path('/var/home/salvogendut/Dev/1986'))
    p.add_argument('--output', type=Path, default=ROOT / 'build/bench/window-repaint-bank-results')
    a = p.parse_args()
    if a.action == 'build': build()
    elif a.action == 'preserve': preserve(a.output)
    else:
        if not a.engine: p.error('run requires --engine')
        run(a.engine,a.output,a.emulator_root)


if __name__ == '__main__': main()

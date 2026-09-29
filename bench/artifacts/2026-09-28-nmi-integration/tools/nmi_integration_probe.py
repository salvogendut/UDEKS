#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the installed deferred NMI service, not cached GUI moves."""
import argparse
import hashlib
import importlib
import json
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from window_completion_probe import window_base, inspect as inspect_completion
from gen_capability_imports import map_exports

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/nmi-integration'
NAME = '2026-09-28-nmi-integration'
STUB = bytes.fromhex('48a9018df5ff6840')
Z80_RETURN = bytes.fromhex('3e3e3200ff0105d53eb1ed793e7e3200ffc9')
Z80_BOOT = bytes.fromhex('3e7e3200ffc30020')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_nmi(data):
    if len(data) != 48 or data[:18] != Z80_RETURN or data[18:26] != STUB:
        raise ValueError('Z80 handoff/NMI code changed')
    if data[29:37] != Z80_BOOT or data[42:44] != b'\xe2\xff':
        raise ValueError('Z80 bootstrap/NMI vector changed')
    drains = int.from_bytes(data[38:40], 'little')
    if data[37] or not drains:
        raise ValueError('NMI was not drained')
    return {'coalesced_drains': drains, 'pending': 0, 'handoff_preserved': True}


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    mapfile = ROOT / 'build/8502/udeks-8502.map'
    text = mapfile.read_text()
    base = window_base(text)
    entry = map_exports(text)['_udeks_window_image_complete'][0]
    source = (ROOT / 'tools/1986_input_smoke.c').read_text()
    boot = '''    idle();
    unsigned initial = word(0xFF0D);'''
    start = '''    idle();
    require(word(0xFFFA)==0xFFE2, "NMI vector not installed");
    unsigned restore_before=word(0xFFF6);
    c128_key_event(machine,SDL_SCANCODE_PAGEUP,true); frames(4);
    c128_key_event(machine,SDL_SCANCODE_PAGEUP,false); frames(4);
    require(word(0xFFF6)>restore_before && byte(0xFFF5)==0, "RESTORE not deferred/drained");
    /* Device writes only: do not patch the handler, OS state or counters. */
    cia_write(&machine->cia2,0xDD04,0); cia_write(&machine->cia2,0xDD05,4);
    cia_write(&machine->cia2,0xDD0D,0x81); cia_write(&machine->cia2,0xDD0E,0x11);
    unsigned initial = word(0xFF0D);'''
    before = '    unsigned cached_leases = word(0xF26C);'
    check = f'''    for(unsigned n=0;n<10000 &&
        (byte(0x{base+20:04X})!=0x8f || byte(0xF27A)!=21);++n) frames(1);
    require(byte(0x{base+20:04X})==0x8f && byte(0xF27A)==21,"wave completion missing");
'''
    finish = '    require(byte(0xF11B) == 0, "lifecycle canary failures");'
    stop = '''    cia_write(&machine->cia2,0xDD0E,0);
    frames(4);
    cia_write(&machine->cia2,0xDD0D,0x7f); (void)cia_read(&machine->cia2,0xDD0D);
    require(byte(0xFFF5)==0 && word(0xFFF6)>100,"NMI stress not drained");
    printf("NMI: RESTORE and CIA2 timer drained %u coalesced events\\n",word(0xFFF6));
'''
    for needle, replacement in ((boot, start), (before, check+before), (finish, check+stop+finish)):
        if source.count(needle) != 1:
            raise ValueError('native integration seam changed')
        source = source.replace(needle, replacement)
    (WORK / 'native.c').write_text(source)
    inputs = ['build/8502/udeks-8502.map', 'build/8502/udeks-8502.bin',
        'build/8502/udeks-8502-panic-probe.map', 'build/user/bootfs.img',
        'src/8502/nmi.s', 'src/8502/nmi-common.inc', 'src/8502/pointer_irq.s',
        'src/8502/z80_handoff.s', 'src/8502/vic_graphics.s', 'include/udeks/memory.h',
        'src/services/window/window_manager.c', 'src/8502/app_gateway.s',
        'tools/1986_input_smoke.c', 'tools/1986_input_smoke_build.py',
        'tools/nmi_integration_probe.py', 'tools/window_completion_probe.py',
        'tools/shadow_boot_probe.py', 'tools/capability_relocation_probe.py',
        'tools/vice_capture.py', 'tools/graphics_cache_placement.py', 'Makefile']
    report = {'qualification': 'installed 8502 deferred NMI; no cached moves or physical qualification',
        'window_base': base, 'completion_entry': entry, 'resident_nmi_charge': 77,
        'remaining_padding': 281, 'binding_bytes': 241, 'remaining_before_manager_delivery': 40,
        'disk_sha256': {fmt: digest(ROOT / 'build/boot' / f'udeks.{fmt}') for fmt in ('d71', 'd64')},
        'inputs_sha256': {n: digest(ROOT / n) for n in inputs},
        'native_sha256': digest(WORK / 'native.c')}
    (WORK / 'build-report.json').write_text(json.dumps(report, indent=2)+'\n')


def verify(report):
    for name, sha in report['inputs_sha256'].items():
        if digest(ROOT / name) != sha:
            raise ValueError('source/build drift '+name)
    for fmt, sha in report['disk_sha256'].items():
        if digest(ROOT / 'build/boot' / f'udeks.{fmt}') != sha:
            raise ValueError('disk drift')
    if digest(WORK / 'native.c') != report['native_sha256']:
        raise ValueError('harness drift')


def decoded(engine, fmt, report):
    return {**inspect_nmi((WORK / f'{engine}-{fmt}-nmi.bin').read_bytes()),
        **inspect_completion((WORK / f'{engine}-{fmt}-windows.bin').read_bytes(),
            (WORK / f'{engine}-{fmt}-gateway.bin').read_bytes(), report['completion_entry'])}


def save_run(engine, provenance, report):
    verify(report)
    result = {fmt: decoded(engine, fmt, report) for fmt in ('d71', 'd64')}
    raw = {p.name: digest(p) for p in WORK.glob(engine+'-*') if p.suffix in ('.bin', '.log')}
    (WORK / f'{engine}-run.json').write_text(json.dumps({'provenance': provenance,
        'decoded': result, 'raw_sha256': raw,
        'build_report_sha256': digest(WORK / 'build-report.json')}, indent=2)+'\n')
    print(json.dumps(result, indent=2), flush=True)


def native():
    from bench_decode import extract_memory
    from graphics_raster_bench_run import emulator_provenance
    report = json.loads((WORK / 'build-report.json').read_text()); verify(report)
    emulator = ROOT.parent / '1986'
    builder = importlib.import_module('1986_input_smoke_build')
    sources = builder.emulator_sources(emulator)
    provenance = emulator_provenance(emulator, sources)
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'sdl3'], text=True))
    runner = WORK / 'native'
    subprocess.run(['cc', '-std=gnu11', '-O2', '-I'+str(emulator / 'src'),
        str(WORK / 'native.c'), *map(str, sources), *flags, '-lm', '-o', str(runner)], check=True)
    for fmt in ('d71', 'd64'):
        snapshot = WORK / f'1986-{fmt}.vsf'
        cmd = [str(runner), str(emulator / 'roms'), str(ROOT / 'build/boot' / f'udeks.{fmt}'),
            builder.slot_address(ROOT / 'build/8502/udeks-scheduler-overlay.map'), str(snapshot)]
        process = subprocess.run(cmd, capture_output=True, text=True)
        (WORK / f'1986-{fmt}.log').write_text(process.stdout+process.stderr)
        print(process.stdout, flush=True)
        if process.returncode:
            raise ValueError('native NMI integration failed')
        memory = snapshot.read_bytes()
        for kind, address, size in (('nmi', 0xffd0, 48),
                ('windows', report['window_base'], 88), ('gateway', 0xcf50, 175)):
            (WORK / f'1986-{fmt}-{kind}.bin').write_bytes(extract_memory(memory, address, size))
    if emulator_provenance(emulator, sources) != provenance:
        raise ValueError('emulator drift')
    save_run('1986', provenance, report)


def vice():
    import shadow_boot_probe as sp
    from capability_relocation_probe import inject_until_state
    from vice_capture import choose_port
    report = json.loads((WORK / 'build-report.json').read_text()); verify(report)
    symbols = sp.symbol_addresses(ROOT / 'build/8502/udeks-8502.map')
    provenance = subprocess.check_output(['flatpak', 'info', 'net.sf.VICE'], text=True)
    for fmt in ('d71', 'd64'):
        port = choose_port()
        process, master = sp.launch_vice(ROOT / 'build/boot' / f'udeks.{fmt}', port, 'net.sf.VICE')
        try:
            time.sleep(6); deadline = time.monotonic()+180
            sp.wait_for_byte(port, sp.ROOT_TERMINAL_STATUS_READY_ADDRESS, 2, deadline)
            # Timer A -> NMI across real Z80 leases and repaint paths.
            sp.write_kernel_blocks(port, [(0xdd04, b'\x00\x04'), (0xdd0d, b'\x81\x11')])
            for command, address in (('xinit', 0xf1b5), ('xclock &', 0xf225), ('xwave &', 0xf265)):
                inject_until_state(port, symbols, command, address, 3, deadline)
            sp.wait_for_byte(port, 0xf27a, 21, deadline)
            sp.wait_for_byte(port, report['window_base']+20, 0x8f, deadline)
            sp.write_kernel_blocks(port, [(0xdd0e, b'\x00')])
            sp.wait_for_byte(port, 0xfff5, 0, deadline)
            sp.write_kernel_blocks(port, [(0xdd0d, b'\x7f')])
            blocks = [('nmi', 0xffd0, 0xffff), ('windows', report['window_base'], report['window_base']+87),
                ('gateway', 0xcf50, 0xcffe)]
            values = sp.capture_blocks(port, [(WORK / f'vice-{fmt}-{kind}.bin', start, end, 'kernel')
                for kind, start, end in blocks])
            for (kind, _, _), value in zip(blocks, values):
                (WORK / f'vice-{fmt}-{kind}.bin').write_bytes(value)
            print(fmt, decoded('vice', fmt, report), flush=True)
        finally:
            sp.terminate(process, port); os.close(master)
    save_run('vice', provenance, report)


def preserve():
    report = json.loads((WORK / 'build-report.json').read_text()); verify(report)
    for engine in ('1986', 'vice'):
        run = json.loads((WORK / f'{engine}-run.json').read_text())
        if run['build_report_sha256'] != digest(WORK / 'build-report.json'):
            raise ValueError('run/build mismatch')
        expected = {f'{engine}-{fmt}-{kind}.bin' for fmt in ('d71', 'd64') for kind in ('nmi', 'windows', 'gateway')}
        if engine == '1986':
            expected |= {f'1986-{fmt}.log' for fmt in ('d71', 'd64')}
        if set(run['raw_sha256']) != expected:
            raise ValueError('missing raw records')
        for name, sha in run['raw_sha256'].items():
            if digest(WORK / name) != sha:
                raise ValueError('raw drift')
        for fmt in ('d71', 'd64'):
            if decoded(engine, fmt, report) != run['decoded'][fmt]:
                raise ValueError('decoded drift')
    artifacts = ROOT / 'bench/artifacts' / NAME
    results = ROOT / 'bench/results' / NAME
    if artifacts.exists() or results.exists():
        raise ValueError('refusing to overwrite evidence')
    artifacts.mkdir(parents=True); results.mkdir(parents=True)
    for name in report['inputs_sha256']:
        dest = artifacts / name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
    for fmt in ('d71', 'd64'):
        shutil.copy2(ROOT / 'build/boot' / f'udeks.{fmt}', artifacts / f'udeks.{fmt}')
    for name in ('native.c', 'build-report.json'):
        shutil.copy2(WORK / name, artifacts / name)
    for path in WORK.iterdir():
        if path.name.startswith(('1986-', 'vice-')) and path.suffix in ('.bin', '.json', '.log'):
            shutil.copy2(path, results / path.name)
    for directory in (artifacts, results):
        paths = sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', '1986', 'vice', 'preserve'))
    args = parser.parse_args()
    {'build': build, '1986': native, 'vice': vice, 'preserve': preserve}[args.action]()

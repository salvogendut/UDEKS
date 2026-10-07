#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prove a guarded bank-1 top-RAM window, not a write-enabled OS image.

No media arguments: this standalone program never accesses IEC or disk data.
Candidate linking is a size gate only; no fake caller provider is advertised.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

from build_scheduler_overlay import map_segments
from graphics_raster_bench_run import emulator_provenance

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'build/bench/storage-window'
CANDIDATE = ROOT/'build/storage-write-placement'
EVIDENCE = '2026-10-07-storage-window'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def placement(segments, blobs):
    groups = {
        'module': (0x1200, 0x1880, ('STARTUP', 'CODE', 'DATA')),
        'policy': (0xb000, 0xc600, ('STORAGECODE',)),
        'driver': (0xe300, 0xe900, ('IECCODE',)),
        'hidden': (0xf000, 0xff00, ('RODATA', 'STORAGEHIGH')),
        'state': (0xe000, 0xe180, ('BSS',)),
    }
    expected = {'ZEROPAGE'} | {s for _, _, names in groups.values() for s in names}
    if set(segments) != expected: raise ValueError('unexpected candidate segments')
    result = {}
    for name, (base, limit, names) in groups.items():
        spans = sorted(segments[s] for s in names)
        end = base
        for first, last, size in spans:
            if first != end or size != last-first+1 or not base <= first <= last < limit:
                raise ValueError(f'{name}: gap, overlap or reservation overflow')
            end = last+1
        if name != 'state' and len(blobs[name]) != end-base:
            raise ValueError(f'{name}: emitted image differs from map')
        result[name] = {'base': base, 'end': end, 'used': end-base, 'free': limit-end}
    first, last, size = segments['ZEROPAGE']
    if first != 2 or last >= 0x20 or size != last-first+1:
        raise ValueError('storage zero page escaped reservation')
    return result


def decode(data, vic):
    if len(data) != 32 or data[:6] != b'SWIN\x01\x02' or data[6] or data[7] != 128:
        raise ValueError('incomplete/failed window proof')
    visible = int.from_bytes(data[8:10], 'little')
    hidden = int.from_bytes(data[10:12], 'little')
    boundary = int.from_bytes(data[12:14], 'little')
    if visible < 128 or hidden < 128 or visible+hidden != 384 or boundary != 128:
        raise ValueError('NMI body/boundary counts differ')
    if data[16:22] != bytes((9 | vic, 9 | vic, 0x7e, 0xff, 0xa5, 0)):
        raise ValueError('mapping/stack/hidden execution/pending mismatch')
    if any(data[14:16]) or any(data[22:]): raise ValueError('nonzero reserved record bytes')
    return {'rounds': data[7], 'visible_nmis': visible, 'hidden_nmis': hidden,
            'boundary_nmis': boundary, 'rcr': data[17], 'common_bytes_compared': 3840}


def negative_image(data):
    # Remove ONLY forwarding of the private pending flag; preserve the rest of
    # the exit sequence, including clearing private state. Must fail code 1.
    pattern = bytes.fromhex('8df5ffa9008d4070')
    if data.count(pattern) != 1: raise ValueError('ambiguous pending-merge patch')
    offset = data.index(pattern)
    result = bytearray(data); result[offset] = 0x2c  # BIT instead of STA
    return bytes(result)


def preserve(run, engine):
    """Archive exact generated artifacts; never silently replace evidence."""
    artifacts = ROOT/'bench/artifacts'/EVIDENCE
    results = ROOT/'bench/results'/EVIDENCE
    artifacts.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    for name in ('probe.prg', 'no-forward.prg', 'module.map', 'module.bin', 'policy.bin', 'driver.bin', 'hidden.bin'):
        dest = artifacts/name
        if dest.exists() and dest.read_bytes() != (run/name).read_bytes():
            raise ValueError('preserved artifact differs; use a new evidence revision: '+name)
        shutil.copyfile(run/name, dest)
    dest = results/(engine+'.json')
    if dest.exists() and dest.read_bytes() != (run/'result.json').read_bytes():
        raise ValueError('preserved result differs; use a new evidence revision: '+engine)
    shutil.copyfile(run/'result.json', dest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=('vice', '1986'), default='vice')
    # Works from the root checkout and its nested build/<branch> worktrees.
    sibling = next((p/'1986' for p in ROOT.parents if (p/'1986/src/c128.h').is_file()), ROOT.parent/'1986')
    parser.add_argument('--emulator', type=Path, default=sibling)
    parser.add_argument('--preserve', action='store_true')
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=args.engine+'-', dir=WORK))
    program = run/'probe.prg'; shutil.copyfile(WORK/'probe.prg', program)
    broken = run/'no-forward.prg'; broken.write_bytes(negative_image(program.read_bytes()))
    # Preserve exact linked candidate too: it is NOT installed by the probe.
    for name in ('module', 'policy', 'driver', 'hidden'):
        shutil.copyfile(CANDIDATE/(name+'.bin'), run/(name+'.bin'))
    shutil.copyfile(CANDIDATE/'module.map', run/'module.map')
    layout = placement(map_segments((run/'module.map').read_text()),
                       {name: (run/(name+'.bin')).read_bytes() for name in ('module', 'policy', 'driver', 'hidden')})
    if args.engine == '1986':
        emulator = args.emulator.resolve()
        sources = importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
        provenance = emulator_provenance(emulator, sources)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'sdl3'], text=True))
        runner = run/'1986-window'
        subprocess.run(['cc', '-std=gnu11', '-O2', '-I'+str(emulator/'src'),
                        str(ROOT/'bench/storage-window/runner.c'), *map(str, sources),
                        *flags, '-lm', '-o', str(runner)], check=True)
    else:
        provenance = subprocess.check_output(['flatpak', 'info', 'net.sf.VICE'], text=True)
    records = []
    for vic, negative in ((0, False), (64, False), (0, True)):
        prg = broken if negative else program
        case = 'no-forward' if negative else f'vic-{vic//64}'
        output = run/(case+'.bin')
        if args.engine == '1986':
            command = [str(runner), str(prg), str(output), str(vic)]
        else:
            command = ['python3', 'tools/vice_capture.py', str(prg), str(output),
                       '--raw-load', '--entry', '0x2800', '--result-address', '0x7000',
                       '--result-size', '32', '--state-offset', '5', '--timeout', '25',
                       '--complete-value', '128' if negative else '2', '--poke', f'0x70f0={vic}']
        with (run/(case+'.log')).open('w') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        raw = output.read_bytes()
        if negative:
            if len(raw) != 32 or raw[:7] != b'SWIN\x01\x80\x01':
                raise ValueError('missing-forward negative control did not fail as expected')
            try: decode(raw, vic)
            except ValueError: pass
            else: raise ValueError('negative passed positive decoder')
            facts = {'negative_control': 'missing pending forwarding rejected'}
        else: facts = decode(raw, vic)
        records.append({'case': case, 'raw': raw.hex(), 'decoded': facts})
        print(f'{args.engine} {case}: {facts}', flush=True)
    if args.engine == '1986' and provenance != emulator_provenance(emulator, sources):
        raise ValueError('1986 inputs changed during qualification')
    files = ('probe.prg', 'no-forward.prg', 'module.map', 'module.bin', 'policy.bin', 'driver.bin', 'hidden.bin')
    sources = ('bench/storage-window/probe.s', 'bench/storage-window/probe.cfg',
               'bench/storage-window/runner.c', 'bench/storage-window/no-caller.s',
               'cfg/8502-storage-write-candidate.cfg', 'mk/storage.mk',
               'src/8502/nmi-common.inc', 'src/services/filesystem/cbm_file.c',
               'src/services/filesystem/cbm_write.c', 'src/services/filesystem/iec_slow.s',
               'src/services/filesystem/iec_service.c', 'src/services/filesystem/fs_namespace.c',
               'src/services/filesystem/iec_entry.s', 'tools/storage_window_probe.py')
    report = {'scope': 'standalone mapping/NMI proof and separate link-size candidate; no storage runtime/OS qualification',
              'engine': args.engine, 'layout': layout, 'records': records, 'provenance': provenance,
              'artifacts': {name: sha(run/name) for name in files},
              'source_sha256': {name: sha(ROOT/name) for name in sources}}
    (run/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    if args.preserve: preserve(run, args.engine)
    print(f'evidence: {run}', flush=True)


if __name__ == '__main__': main()

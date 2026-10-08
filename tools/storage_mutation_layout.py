#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repeat the compact mutation-service link in isolated output files.

The candidate uses the production memory reservations and existing service
objects, but a separate output directory. A failed link cannot replace boot
images. Historical pre-integration failures remain in preserved evidence.
"""
import hashlib
import json
import argparse
from pathlib import Path
import subprocess
import sys
from build_scheduler_overlay import map_segments

ROOT = Path(__file__).resolve().parents[1]
REGIONS = {
    'CODE': (0x1200, 0x1880, ('STARTUP', 'CODE', 'DATA')),
    'STORAGECODE': (0xb000, 0xc600, ('STORAGECODE',)),
    'BSS': (0xe000, 0xe180, ('BSS',)),
    'IECCODE': (0xe300, 0xe900, ('IECCODE',)),
    'STORAGEHIGH': (0xf000, 0xff00, ('RODATA', 'STORAGEHIGH')),
}


def headroom(text, *, allow_overflow=False):
    segments = map_segments(text)
    allowed = {'ZEROPAGE'} | {n for _, _, names in REGIONS.values() for n in names}
    if segments.keys() - allowed:
        raise ValueError('unexpected storage segment')
    result = {}
    for region, (start, limit, names) in REGIONS.items():
        end = start
        for name in names:
            if name == 'DATA' and name not in segments:
                continue
            if name not in segments:
                raise ValueError(f'missing storage segment: {name}')
            first, last, size = segments[name]
            if first != end or last + 1 - first != size or not size or (last >= limit and not allow_overflow):
                raise ValueError(f'{name} moved or exceeds its guarded reservation')
            end = last + 1
        result[region] = limit - end
    result['code_total'] = sum(value for name, value in result.items() if name != 'BSS')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', action='store_true', help='also measure candidate request handlers')
    args = parser.parse_args()
    directory = 'build/storage-mutation-policy' if args.policy else 'build/storage-mutation-layout'
    target = ROOT / directory
    target.mkdir(parents=True,exist_ok=True)
    # These are this tool's generated reports, never user media. A failed
    # rebuild must not leave an earlier successful qualification masquerading
    # as its result, or let a stale linker map supply its budget.
    (target/'result.json').unlink(missing_ok=True)
    (target/'module.map').unlink(missing_ok=True)
    cfg = (ROOT/'cfg/8502-storage.cfg').read_text()
    if cfg.count('build/storage/')!=3:
        raise ValueError('production split-output layout changed')
    (target/'candidate.cfg').write_text(cfg.replace('build/storage/', directory+'/'))
    flags = ['-t','none','--cpu','6502','--standard','c99','-Os','--static-locals',
             '-I','include','-D','UDEKS_IEC_WRITE','-D','UDEKS_IEC_MUTATE']
    subprocess.run(['ca65','--cpu','6502','-D','UDEKS_IEC_ASYNC','-o',str(target/'cbm_mutate.o'),
                    'src/services/filesystem/mutation_6502.s'],cwd=ROOT,check=True)
    subprocess.run(['ca65','--cpu','6502','-D','UDEKS_IEC_WRITE','-D','UDEKS_IEC_MUTATE',
                    '-D','UDEKS_IEC_ASYNC',
                    '-D','UDEKS_STORAGE_MODULE','-o',str(target/'iec_slow.o'),
                    'src/services/filesystem/iec_slow.s'],cwd=ROOT,check=True)
    objects = [ROOT/'build/storage'/f'{name}.o' for name in (
        'iec_lease','iec_context','iec_service','fs_namespace','cbm_file','cbm_write')]
    subprocess.run(['cl65',*flags,'-D','UDEKS_STORAGE_HIGH','-D','UDEKS_COMPACT_STATUS',
                    '--code-name','STORAGECODE','-c','-o',str(target/'cbm_write.o'),
                    'src/services/filesystem/cbm_write.c'],cwd=ROOT,check=True)
    objects[5] = target/'cbm_write.o'
    if args.policy:
        subprocess.run(['cl65', *flags, '-D', 'UDEKS_STORAGE_WRITES', '-D', 'UDEKS_STORAGE_LEASE',
                        '-D', 'UDEKS_STORAGE_MUTATIONS', '--code-name', 'STORAGECODE',
                        '-c', '-o', str(target/'iec_service.o'),
                        'src/services/filesystem/iec_service.c'], cwd=ROOT, check=True)
        objects[2] = target/'iec_service.o'
    objects += [target/'iec_slow.o',target/'cbm_mutate.o']
    link = subprocess.run(['cl65','-t','none','-C',str(target/'candidate.cfg'),
                    '-m',str(target/'module.map'),'-o',str(target/'module.bin'),
                    *map(str,objects)],cwd=ROOT, capture_output=True, text=True)
    (target/'link.log').write_text(link.stdout+link.stderr)
    if not (target/'module.map').exists():
        raise RuntimeError('link failed without a map: '+link.stderr)
    sources = ['cfg/8502-storage.cfg','src/services/filesystem/mutation_6502.s',
               'src/services/filesystem/cbm_write.c',
               'src/services/filesystem/iec_slow.s','src/services/filesystem/namespace_6502.s']
    if args.policy:
        sources += ['src/services/filesystem/iec_service.c', 'include/udeks/file_mutation.h']
    result = dict(scope='candidate policy link only; not installed or runtime-qualified' if args.policy else
                  'link/placement proof only; no public handlers, no runtime qualification',
                  link_passed=link.returncode == 0,
                  production=headroom((ROOT/'build/storage/module.map').read_text()),
                  with_backend=headroom((target/'module.map').read_text(), allow_overflow=bool(link.returncode)),
                  inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
    (target/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if link.returncode:
        print(link.stderr, file=sys.stderr)
        return 1  # diagnostics are NOT a successful placement gate
    return 0


if __name__=='__main__': sys.exit(main())

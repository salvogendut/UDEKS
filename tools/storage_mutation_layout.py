#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Link the private mutation backend beside the real service, WITHOUT shipping it.

The candidate uses the production memory reservations and existing service
objects, but a separate output directory. No public operation or long DOS wait
is enabled in boot images by this measurement.
"""
import hashlib
import json
from pathlib import Path
import subprocess
from build_scheduler_overlay import map_segments

ROOT = Path(__file__).resolve().parents[1]
REGIONS = {
    'CODE': (0x1200, 0x1880, ('STARTUP', 'CODE', 'DATA')),
    'STORAGECODE': (0xb000, 0xc600, ('STORAGECODE',)),
    'BSS': (0xe000, 0xe180, ('BSS',)),
    'IECCODE': (0xe300, 0xe900, ('IECCODE',)),
    'STORAGEHIGH': (0xf000, 0xff00, ('RODATA', 'STORAGEHIGH')),
}


def headroom(text):
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
            if first != end or last + 1 - first != size or not size or last >= limit:
                raise ValueError(f'{name} moved or exceeds its guarded reservation')
            end = last + 1
        result[region] = limit - end
    result['code_total'] = sum(value for name, value in result.items() if name != 'BSS')
    return result


def main():
    target = ROOT/'build/storage-mutation-layout'
    target.mkdir(parents=True,exist_ok=True)
    cfg = (ROOT/'cfg/8502-storage.cfg').read_text()
    if cfg.count('build/storage/')!=3:
        raise ValueError('production split-output layout changed')
    (target/'candidate.cfg').write_text(cfg.replace('build/storage/','build/storage-mutation-layout/'))
    flags = ['-t','none','--cpu','6502','--standard','c99','-Os','--static-locals',
             '-I','include','-D','UDEKS_IEC_WRITE','-D','UDEKS_IEC_MUTATE']
    subprocess.run(['cl65',*flags,'--code-name','STORAGEHIGH','-c','-o',str(target/'cbm_mutate.o'),
                    'src/services/filesystem/cbm_mutate.c'],cwd=ROOT,check=True)
    subprocess.run(['ca65','--cpu','6502','-D','UDEKS_IEC_WRITE','-D','UDEKS_IEC_MUTATE',
                    '-D','UDEKS_STORAGE_MODULE','-o',str(target/'iec_slow.o'),
                    'src/services/filesystem/iec_slow.s'],cwd=ROOT,check=True)
    objects = [ROOT/'build/storage'/f'{name}.o' for name in (
        'iec_lease','iec_context','iec_service','fs_namespace','cbm_file','cbm_write')]
    objects += [target/'iec_slow.o',target/'cbm_mutate.o']
    subprocess.run(['cl65','-t','none','-C',str(target/'candidate.cfg'),
                    '-m',str(target/'module.map'),'-o',str(target/'module.bin'),
                    *map(str,objects)],cwd=ROOT,check=True)
    sources = ['cfg/8502-storage.cfg','src/services/filesystem/cbm_mutate.c',
               'src/services/filesystem/iec_slow.s','src/services/filesystem/namespace_6502.s']
    result = dict(scope='link/placement proof only; no public handlers, no runtime qualification',
                  production=headroom((ROOT/'build/storage/module.map').read_text()),
                  with_backend=headroom((target/'module.map').read_text()),
                  inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
    (target/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()

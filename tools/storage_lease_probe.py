#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the actual guarded write service on NEW disposable VICE media only.

No input-media option. This does not install the service into a UDEKS boot disk
or qualify scheduler ownership/exit routing; the probe supplies trusted IDs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from storage_write_probe import make_disk, read_files, KEEP
from build_scheduler_overlay import map_segments

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = '2026-10-07-storage-lease'
BLOBS = ('module.bin', 'policy.bin', 'driver.bin', 'hidden.bin', 'module.map')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def layout(segments, blobs):
    groups = {
        'module': (0x1200, 0x1880, ('STARTUP', 'CODE')),
        'policy': (0xb000, 0xc600, ('STORAGECODE',)),
        'driver': (0xe300, 0xe900, ('IECCODE',)),
        'hidden': (0xf000, 0xff00, ('RODATA', 'STORAGEHIGH')),
        'state': (0xe000, 0xe180, ('BSS',)),
    }
    if set(segments) != {'ZEROPAGE'} | {s for _, _, ns in groups.values() for s in ns}:
        raise ValueError('unexpected service segments')
    answer = {}
    for group, (base, limit, names) in groups.items():
        end = base
        for first, last, size in sorted(segments[n] for n in names):
            if first != end or not first <= last < limit or size != last-first+1:
                raise ValueError('service gap/overlap/overflow: '+group)
            end = last+1
        if group != 'state' and len(blobs[group+'.bin']) != end-base:
            raise ValueError('service binary/map mismatch: '+group)
        answer[group] = {'start': base, 'used': end-base, 'free': limit-end}
    if segments['ZEROPAGE'] != (2, 0x1b, 0x1a): raise ValueError('runtime zero page moved')
    return answer


def decode(record, vic):
    expected = bytearray(b'SLSE\x01\x02'+bytes(26))
    expected[10:15] = bytes((27, 3, 1, 0, 1))
    expected[16:21] = bytes((9|vic, 9|vic, 0x7e, 0, 0xe2))
    if record != expected: raise ValueError('lease probe failed: '+record.hex())
    return {'requests': 27, 'cleanups': 3, 'hidden_nmis_forwarded': 1,
            'service_stack_restored': 0xe200, 'rcr': 9|vic}


def negative_image(program, driver):
    """Remove only the real lease's pending publication, not the test stub."""
    pattern = bytes.fromhex('8df5ffa9008d')
    if program.count(driver) != 1 or driver.count(pattern) != 1:
        raise ValueError('ambiguous real-service NMI forwarding patch')
    offset = program.index(driver)+driver.index(pattern)
    result = bytearray(program); result[offset] = 0x2c  # BIT replaces STA
    return bytes(result)


def decode_negative(record, vic):
    expected = bytearray(b'SLSE\x01\x80\x05\x01'+bytes(24))
    expected[10] = expected[12] = 1
    expected[16] = 9|vic
    if record != expected: raise ValueError('missing-forward control did not fail as expected')
    return {'negative_control': 'real lease missing NMI forwarding detected'}


def preserve(work, case):
    artifacts = ROOT/'bench/artifacts'/EVIDENCE
    results = ROOT/'bench/results'/EVIDENCE
    artifacts.mkdir(parents=True, exist_ok=True); results.mkdir(parents=True, exist_ok=True)
    for name in ('probe.prg', 'no-forward.prg', *BLOBS):
        dest = artifacts/name
        if dest.exists() and dest.read_bytes() != (work/name).read_bytes():
            raise ValueError('artifact changed; use a new evidence revision: '+name)
        shutil.copyfile(work/name, dest)
    dest = results/(case+'.json')
    if dest.exists() and dest.read_bytes() != (work/'result.json').read_bytes():
        raise ValueError('result changed; use a new evidence revision: '+case)
    shutil.copyfile(work/'result.json', dest)


def run(drive, vic, keep, negative=False):
    base = ROOT/'build/bench/storage-lease'; base.mkdir(parents=True, exist_ok=True)
    case = drive+'-vic'+str(vic//64)+('-no-forward' if negative else '')
    work = Path(tempfile.mkdtemp(prefix=case+'-', dir=base))
    shutil.copyfile(base/'probe.prg', work/'probe.prg')
    for name in BLOBS: shutil.copyfile(ROOT/'build/storage-write-lease'/name, work/name)
    (work/'no-forward.prg').write_bytes(negative_image(
        (work/'probe.prg').read_bytes(), (work/'driver.bin').read_bytes()))
    placement = layout(map_segments((work/'module.map').read_text()),
                       {n: (work/n).read_bytes() for n in BLOBS if n.endswith('.bin')})
    extension = {'1541':'d64', '1571':'d71', '1581':'d81'}[drive]
    disk = work/('disposable.'+extension)
    original = make_disk(drive); disk.write_bytes(original)
    (work/('before.'+extension)).write_bytes(original)
    command = ['python3', 'tools/vice_capture.py', str(work/('no-forward.prg' if negative else 'probe.prg')), str(work/'record.bin'),
               '--raw-load', '--entry', '0x2800', '--result-address', '0xa000',
               '--result-size', '32', '--state-offset', '5', '--complete-value', '128' if negative else '2',
               '--timeout', '120', '--poll-delay', '4', '--capture-incomplete',
               '--poke', f'0xa0f0={vic}', '--vice-arg=-drive8truedrive',
               '--vice-arg=-drive8type', '--vice-arg='+drive, '--vice-arg=-8', '--vice-arg='+str(disk)]
    with (work/'vice.log').open('w') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raw = (work/'record.bin').read_bytes().hex() if (work/'record.bin').exists() else 'no record'
        raise RuntimeError(f'{case}: {raw}; see {work}')
    record = (work/'record.bin').read_bytes()
    facts = decode_negative(record, vic) if negative else decode(record, vic)
    actual = read_files(disk.read_bytes(), drive)
    expected = {'KEEP': KEEP} if negative else {'KEEP': KEEP, 'LEASE': bytes(range(51)), 'EMPTY': b''}
    if actual != expected:
        raise ValueError('unexpected on-disk content: '+repr(actual))
    if negative and disk.read_bytes() != original: raise ValueError('negative control changed media')
    source_names = ('src/services/filesystem/iec_lease.s', 'src/services/filesystem/iec_service.c',
                    'src/services/filesystem/cbm_file.c', 'src/services/filesystem/cbm_write.c',
                    'src/services/filesystem/iec_slow.s', 'src/services/filesystem/fs_namespace.c',
                    'include/udeks/storage_write.h', 'cfg/8502-storage-write-lease.cfg',
                    'bench/storage-lease/entry.s', 'bench/storage-lease/main.c',
                    'bench/storage-lease/probe.cfg', 'tools/storage_lease_probe.py', 'mk/storage.mk')
    report = {'scope': 'actual linked bank-1 service on disposable media; not installed OS/lifecycle integration',
              'drive': drive, 'vic': vic, 'negative': negative, 'record': record.hex(), 'decoded': facts,
              'layout': placement, 'files': {n: data.hex() for n, data in actual.items()},
              'disk_before': hashlib.sha256(original).hexdigest(), 'disk_after': sha(disk),
              'artifacts': {n: sha(work/n) for n in ('probe.prg', 'no-forward.prg', *BLOBS)},
              'source_sha256': {n: sha(ROOT/n) for n in source_names},
              'vice': subprocess.check_output(['flatpak', 'info', 'net.sf.VICE'], text=True)}
    (work/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    if keep: preserve(work, case)
    print(f'{case}: {facts}; disk contents verified. Evidence: {work}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--drive', choices=('1541','1571','1581','all'), default='all')
    parser.add_argument('--vic', choices=(0,64), type=int, default=0)
    parser.add_argument('--preserve', action='store_true')
    parser.add_argument('--negative', action='store_true', help='omit real pending forwarding; must fail before any write')
    args = parser.parse_args()
    for drive in (('1541','1571','1581') if args.drive=='all' else (args.drive,)):
        run(drive, args.vic, args.preserve, args.negative)


if __name__ == '__main__': main()

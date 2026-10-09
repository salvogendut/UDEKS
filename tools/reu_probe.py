#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the standalone REU candidate in VICE; never boot or modify an OS disk."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(data, banks):
    if len(data) != 32 or data[:5] != b'REUQ\x01':
        raise ValueError('invalid REU qualification record')
    if data[5] != 2 or data[6]:
        raise ValueError(f'REU probe failed/incomplete: state={data[5]}, failure={data[6]}')
    if banks not in (0, 2, 4, 8, 16) or data[7] != banks:
        raise ValueError('configuration mismatch')
    cases = int.from_bytes(data[8:10], 'little')
    calls = int.from_bytes(data[10:12], 'little')
    expected = (128, 265 + 3*banks, 8, banks, min(banks, 8), 0, banks) if banks else (0, 1, 0, 0, 0, 19, 0)
    if (cases, calls, *data[12:17]) != expected:
        raise ValueError('coverage/capacity/restoration counters differ')
    if any(data[17:]):
        raise ValueError('nonzero reserved bytes')
    return {'configured_kib': banks*64, 'usable_prefix_kib': data[14]*64,
            'roundtrips': cases, 'checked_transport_calls': calls,
            'invalid_requests_rejected': data[12], 'distinct_banks': data[13],
            'capacity_preimages_verified': data[16], 'capacity_errno': data[15]}


def misbanked_image(data):
    """Negative control: force the transfer's bank-1 selector to bank 0."""
    pattern = bytes.fromhex('09408d06d5')
    if data.count(pattern) != 1:
        raise ValueError('bank-selection fault patch is ambiguous')
    patched = bytearray(data)
    patched[data.index(pattern)+1] = 0
    return bytes(patched)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    build = ROOT/'build/reu'
    if not (build/'probe.prg').is_file():
        raise SystemExit('first run: distrobox-enter my-distrobox -- make reu-probe-build')
    output = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix='vice-', dir=build))
    if args.output:
        output.mkdir(parents=True, exist_ok=False)
    for name in ('probe.prg', 'probe.map'):
        shutil.copyfile(build/name, output/name)
    faulty = output/'misbanked.prg'
    faulty.write_bytes(misbanked_image((output/'probe.prg').read_bytes()))
    provenance = subprocess.check_output(['flatpak', 'info', 'net.sf.VICE'], text=True)
    records = []
    for kib, negative in ((0, False), (128, False), (256, False), (512, False), (1024, False), (512, True)):
        name = 'misbanked' if negative else f'vice-{kib}'
        program = faulty if negative else output/'probe.prg'
        capture = output/(name+'.bin')
        command = [sys.executable, str(ROOT/'tools/vice_capture.py'), str(program), str(capture),
                   '--raw-load', '--entry', '0x2800', '--result-address', '0x7000',
                   '--result-size', '32', '--state-offset', '5', '--timeout', '25',
                   '--capture-incomplete', '--poke', f'0x70f0={kib//64}']
        if kib:
            command += ['--vice-arg=-reu', '--vice-arg=-reusize', f'--vice-arg={kib}']
        else:
            command += ['--vice-arg=+reu']
        if negative:
            command += ['--complete-value', '128']
        with (output/(name+'.log')).open('w') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        raw = capture.read_bytes()
        if negative:
            if len(raw) != 32 or raw[:7] != b'REUQ\x01\x80\x0a':
                raise ValueError('wrong DMA bank did not fail the target comparison')
            try:
                decode(raw, 8)
            except ValueError:
                pass
            else:
                raise ValueError('negative control accepted as a success')
            facts = {'negative_control': 'wrong DMA bank rejected at target comparison'}
        else:
            facts = decode(raw, kib//64)
        records.append({'case': name, 'raw': raw.hex(), 'decoded': facts})
        print(f'{name}: {facts}', flush=True)
    sources = ('src/services/memory/reu.s', 'src/services/memory/reu_capacity.c',
               'include/udeks/reu.h', 'bench/reu/probe.s', 'bench/reu/probe.cfg',
               'mk/reu.mk', 'tools/reu_probe.py', 'tools/vice_capture.py')
    report = {'scope': 'standalone transport/capacity candidate, NOT an installed graphics backend',
              'emulator': provenance, 'records': records,
              'source_sha256': {name: digest(ROOT/name) for name in sources},
              'artifact_sha256': {name: digest(output/name) for name in ('probe.prg', 'probe.map', 'misbanked.prg')}}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'evidence: {output}', flush=True)


if __name__ == '__main__':
    main()

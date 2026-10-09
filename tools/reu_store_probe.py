#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the private REU object-store candidate, never an installed OS backend."""
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
    if len(data) != 32 or data[:5] != b'RSTQ\x01':
        raise ValueError('invalid REU store qualification record')
    if banks not in (0, 2, 4, 8, 16):
        raise ValueError('unsupported qualification configuration')
    expected = bytearray(32)
    expected[:10] = b'RSTQ\x01\x02\x00'+bytes([banks, min(banks, 8), 7 if banks else 1])
    if banks:
        # Four independent 8 KiB extents, sequential writes with four chunk
        # lengths, 30-byte row reads, one partial failed write and one reuse.
        writes = sum((8192+n-1)//n for n in (19, 255, 256, 31))
        calls = writes + 4*((8192+29)//30) + 3
        expected[10:12] = calls.to_bytes(2, 'little')
        expected[12:14] = (32769).to_bytes(2, 'little')
        expected[14:19] = bytes((14, 1, 2, 6, 0))
    else:
        expected[14] = 1
    expected[19] = 39  # real cc65 metadata, not host C struct padding
    if data != expected:
        raise ValueError(f'incomplete/failed store proof or wrong coverage: {data.hex()}')
    return {'configured_kib': banks*64, 'verified_prefix_kib': min(banks, 8)*64,
            'offered_kib': 32 if banks else 0,
            'checked_io_calls': int.from_bytes(data[10:12], 'little'),
            'verified_bytes': int.from_bytes(data[12:14], 'little'),
            'rejections': data[14], 'injected_partial_faults': data[15],
            'host_banks_guarded': data[16], 'metadata_bytes': data[19]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    build = ROOT/'build/reu-store'
    if not (build/'probe.prg').is_file():
        raise SystemExit('first run: distrobox-enter my-distrobox -- make reu-store-build')
    output = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix='vice-', dir=build))
    if args.output:
        output.mkdir(parents=True, exist_ok=False)
    for name in ('probe.prg', 'probe.map'):
        shutil.copyfile(build/name, output/name)
    provenance = subprocess.check_output(['flatpak', 'info', 'net.sf.VICE'], text=True)
    records = []
    for kib, negative in ((0, False), (128, False), (256, False), (512, False), (1024, False), (512, True)):
        name = 'corrupt-read' if negative else f'vice-{kib}'
        capture = output/(name+'.bin')
        command = [sys.executable, str(ROOT/'tools/vice_capture.py'), str(output/'probe.prg'), str(capture),
                   '--raw-load', '--entry', '0x2800', '--result-address', '0x7000',
                   '--result-size', '32', '--state-offset', '5', '--timeout', '45',
                   '--capture-incomplete', '--poke', f'0x70f0={kib//64}',
                   '--poke', f'0x70f1={int(negative)}']
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
            if len(raw) != 32 or raw[:7] != b'RSTQ\x01\x80\x09':
                raise ValueError('corrupt readback did not fail independent byte comparison')
            try:
                decode(raw, 8)
            except ValueError:
                pass
            else:
                raise ValueError('negative control accepted')
            facts = {'negative_control': 'corrupt readback rejected at independent comparison'}
        else:
            facts = decode(raw, kib//64)
        records.append({'case': name, 'raw': raw.hex(), 'decoded': facts})
        print(f'{name}: {facts}', flush=True)
    sources = ('src/services/memory/reu.s', 'src/services/memory/reu_capacity.c',
               'src/services/memory/reu_store.c', 'include/udeks/reu.h', 'include/udeks/reu_store.h',
               'bench/reu/store_probe.s', 'bench/reu/store_probe.c', 'bench/reu/store_probe.cfg',
               'mk/reu.mk', 'mk/reu_store.mk', 'tools/reu_store_probe.py', 'tools/vice_capture.py')
    report = {'scope': 'standalone owned REU store; NOT installed, no live desktop/IRQ/NMI claim',
              'emulator': provenance, 'records': records,
              'source_sha256': {name: digest(ROOT/name) for name in sources},
              'artifact_sha256': {name: digest(output/name) for name in ('probe.prg', 'probe.map')}}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (output/'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in sorted(output.iterdir())
                                          if p.is_file() and p.name != 'SHA256SUMS'))
    print(f'evidence: {output}', flush=True)


if __name__ == '__main__':
    main()

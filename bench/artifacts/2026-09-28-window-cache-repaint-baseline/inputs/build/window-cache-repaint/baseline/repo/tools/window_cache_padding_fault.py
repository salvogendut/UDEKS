#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Negative control: remove capture tail masking without changing valid pixels."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from window_cache_bench import decode_matrix

ROOT = Path(__file__).resolve().parents[1]


def make_fault(work):
    original = (work / 'cache-matrix.prg').read_bytes()
    symbols = (work / 'cache-matrix.map').read_text()
    def address(name):
        match = re.search(r'\b' + re.escape(name) + r'\s+([0-9A-Fa-f]{6})\s+RLA', symbols)
        if match is None: raise ValueError(f'missing linked symbol {name}')
        return int(match[1], 16)
    start, end = address('_cache_capture_row'), address('_cache_paste_row')
    mask = address('_cache_row_last_mask')
    load = int.from_bytes(original[:2], 'little')
    needle = b'\x2d' + mask.to_bytes(2, 'little')  # AND abs, only inside capture
    begin, stop = start - load + 2, end - load + 2
    if original[begin:stop].count(needle) != 1:
        raise ValueError('capture mask instruction is not unique; refusing mutation')
    offset = original.index(needle, begin, stop)
    mutated = bytearray(original)
    mutated[offset:offset+3] = b'\xea\xea\xea'
    program = work / 'cache-padding-negative.prg'
    program.write_bytes(mutated)
    mutation = {'reference_sha256': hashlib.sha256(original).hexdigest(),
                'negative_sha256': hashlib.sha256(mutated).hexdigest(),
                'instruction_address': load + offset - 2,
                'original': needle.hex(), 'replacement': 'eaeaea'}
    (work / 'padding-mutation.json').write_text(json.dumps(mutation, indent=2) + '\n')
    return program, mutation


def check_fault(data):
    if len(data) != 8096 or data[7] != 3:
        raise ValueError('negative control did not signal captured padding failure 3')
    corrected = bytearray(data)
    corrected[7] = 0
    # This deliberately proves every displayed pixel/dirty flag still matches.
    result = decode_matrix(corrected)
    try: decode_matrix(data)
    except ValueError: pass
    else: raise ValueError('decoder accepted the known malformed packed image')
    return {'expected_failure': 3, 'checks': result['checks'],
            'pixels_still_match': True, 'raw_sha256': hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=('1986', 'vice'), required=True)
    parser.add_argument('--work', type=Path, default=ROOT / 'build/window-cache-asm')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/window-cache-asm-results')
    args = parser.parse_args()
    program, mutation = make_fault(args.work)
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / f'{args.engine}-padding-negative.bin'
    if args.engine == '1986':
        command = [str(args.work / '1986-cache-bench'), str(program), str(output), 'WROW']
    else:
        command = ['python3', str(ROOT / 'tools/vice_capture.py'), str(program), str(output),
                   '--entry', '0x2000', '--result-address', '0x7fc0', '--result-size', '8096',
                   '--state-offset', '5', '--raw-load', '--timeout', '90']
    subprocess.run(command, check=True)
    report = {'mutation': mutation, 'record': check_fault(output.read_bytes())}
    (args.output / f'{args.engine}-padding-negative.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

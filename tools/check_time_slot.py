#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the actual 6502 guard/registration candidate, NOT a boot overlay.

The Python image validator is an independent oracle for header mutations.
The C fixture also exercises state transitions and the exact sealed module.
CIA addresses are ordinary simulator RAM, not hardware qualification.
"""
import json
import hashlib
from pathlib import Path
import re
import struct
import subprocess

from service_image import checksum, validate, TIME_BASE, TIME_LIMIT
from time_module_layout import segments

ROOT = Path(__file__).resolve().parents[1]


def validation_cases(original):
    """Records: offset, width, value LE, received length LE, invalid flag.

    Width 3 deliberately corrupts the checksum; widths 1/2 reseal it so
    malformed metadata cannot pass merely because checksums catch it first.
    """
    size = len(original)
    records = []

    def add(offset, width, value, received=size):
        data = bytearray(original)
        if width in (1, 3):
            data[offset] = value
        elif width == 2:
            struct.pack_into('<H', data, offset, value)
        if width != 3:
            struct.pack_into('<H', data, 16, checksum(data))
        supplied = bytes(data[:received]) + bytes(max(0, received - size))
        try:
            validate(supplied)
            invalid = 0
        except ValueError:
            invalid = 1
        records.append(struct.pack('<BBHHB', offset, width, value, received, invalid))

    add(0, 0, 0)
    for offset in range(48):
        if offset in (16, 17):
            continue
        for bit in range(8):
            add(offset, 1, original[offset] ^ (1 << bit))
    for offset in (16, 17):
        add(offset, 3, original[offset] ^ 1)
    for received in (0, 1, 47, 48, size-1, size+1, TIME_LIMIT-TIME_BASE, 0xffff):
        add(0, 0, 0, received)
    for value in (0, 1, 47, 48, 49, size-1, size+1, 0x100, 0x1000, 0xffff):
        add(10, 2, value)
    for value in (0, 1, TIME_LIMIT-TIME_BASE-size,
                  TIME_LIMIT-TIME_BASE-size+1, 0xffff-size, 0x10000-size, 0xffff):
        add(12, 2, value)
    for offset in (20, 42, 44, 46):
        for value in (0, TIME_BASE-1, TIME_BASE, TIME_BASE+47, TIME_BASE+48,
                      TIME_BASE+size-1, TIME_BASE+size, TIME_LIMIT-1, TIME_LIMIT, 0xffff):
            add(offset, 2, value)
    return b''.join(records)


def main():
    out = ROOT/'build/services/time'
    report_path = out/'slot-check.json'
    report_path.unlink(missing_ok=True)
    data = (out/'TIME.SVC').read_bytes()
    validate(data)
    cases = validation_cases(data)
    (out/'slot-cases.bin').write_bytes(cases)

    def run(*cmd):
        subprocess.run(cmd, cwd=ROOT, check=True)

    objects = []
    for name, source in (
        ('slot-core', 'src/services/module/time_slot.s'),
        ('slot-start', 'src/8502/service_start.s'),
        ('slot-fixture', 'bench/time-module/slot_fixture.s'),
        ('slot-runtime', 'src/services/time/runtime.s'),
    ):
        obj = out/(name+'.o')
        run('ca65', '-D', 'UDEKS_TIME_SLOT_TEST', '-o', str(obj), source)
        objects.append(str(obj))
    run('ld65', '-C', 'bench/time-module/slot.cfg', '-m', str(out/'slot.map'),
        '-o', str(out/'slot.bin'), *objects)
    embed = out/'slot-embed.s'
    embed.write_text(
        '.export _module_image, _slot_image, _slot_size, _validation_cases, _validation_count\n'
        '.segment "RODATA"\n'
        '_module_image: .incbin "build/services/time/TIME.SVC"\n'
        '_slot_image: .incbin "build/services/time/slot.bin"\n'
        f'_slot_size: .word {len((out/"slot.bin").read_bytes())}\n'
        '_validation_cases: .incbin "build/services/time/slot-cases.bin"\n'
        f'_validation_count: .word {len(cases)//7}\n')
    harness = []
    for name, source in (('slot-check', 'bench/time-module/slot_check.c'),
                         ('slot-call', 'bench/time-module/call.s'),
                         ('slot-embed', str(embed))):
        obj = out/(name+'.o')
        run('cl65', '-t', 'sim6502', '-Oirs', '-c', '-o', str(obj), source)
        harness.append(str(obj))
    run('cl65', '-t', 'sim6502', '-m', str(out/'slot-check.map'),
        '-o', str(out/'slot-check.sim65'), *harness)
    # The simulator's own code/data must not overlap the separately loaded
    # fixture. Enforce this, rather than hoping future test growth fits.
    from build_scheduler_overlay import map_segments
    layout = map_segments((out/'slot-check.map').read_text())
    if any(end >= 0x8000 for name, (start, end, _) in layout.items()
           if name != 'ZEROPAGE'):
        raise ValueError('simulator test program overlaps the manager fixture')
    proof = subprocess.run(['sim65', str(out/'slot-check.sim65')], cwd=ROOT,
                           capture_output=True, text=True, timeout=60)
    (out/'slot-check.log').write_text(proof.stdout+proof.stderr)
    print(proof.stdout, end='')
    print(proof.stderr, end='')
    proof.check_returncode()
    # Prove that these cases execute the new validator, not only the Python
    # oracle. Disable BOTH checksum-rejection branches in the fixture binary;
    # the unchanged harness must fail at its first checksum-corruption case.
    fixture = (out/'slot.bin').read_bytes()
    pattern = rb'\xa5\x16\xcd\x10\x93\xd0.\xa5\x17\xcd\x11\x93\xd0.\x18\x60'
    matches = list(re.finditer(pattern, fixture, re.DOTALL))
    if len(matches) != 1:
        raise ValueError('checksum negative-control instruction changed')
    negative = bytearray(fixture)
    for offset in (5, 12):
        start = matches[0].start()+offset
        negative[start:start+2] = b'\xea\xea'
    (out/'slot-negative.bin').write_bytes(negative)
    negative_embed = out/'slot-negative-embed.s'
    negative_embed.write_text(embed.read_text().replace('time/slot.bin', 'time/slot-negative.bin'))
    run('ca65', '-o', str(out/'slot-negative-embed.o'), str(negative_embed))
    run('cl65', '-t', 'sim6502', '-o', str(out/'slot-negative.sim65'),
        *harness[:2], str(out/'slot-negative-embed.o'))
    failed = subprocess.run(['sim65', str(out/'slot-negative.sim65')], cwd=ROOT,
                            capture_output=True, text=True, timeout=60)
    (out/'slot-negative.log').write_text(failed.stdout+failed.stderr)
    first_bad_sum = next(i for i in range(len(cases)//7) if cases[i*7+1] == 3)
    if not failed.returncode or f'case {first_bad_sum}:' not in failed.stdout:
        raise AssertionError('negative control did not detect disabled checksum rejection')
    print('PASS negative control: disabled checksum rejection detected')
    sizes = segments(out/'slot-core.o')
    report = dict(scope='sim6502 candidate only; not installed in boot',
                  validation_cases=len(cases)//7, startup_results=256,
                  core_segments=sizes, core_bytes=sum(sizes.values()),
                  startup_segments=segments(out/'slot-start.o'),
                  negative_control='checksum rejection disabled: detected',
                  module_sha256=hashlib.sha256(data).hexdigest(),
                  fixture_sha256=hashlib.sha256(fixture).hexdigest(),
                  cia='RAM-backed, not hardware timing')
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

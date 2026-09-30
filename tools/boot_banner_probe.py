#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold-boot actual header checks, including deliberately corrupt identities.

Only disposable copies are changed. Corrupting an identity does not change
the service code; the normal disk shell still boots, letting us inspect the
banner without invoking an invalid recovery filesystem.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from build_d71 import sector_offset
from managed_app_fixture import dos_file
from shadow_boot_probe import launch_vice, wait_for_byte, capture_blocks, terminate
from storage_shell_probe import console_address
from vice_capture import choose_port

ROOT = Path(__file__).resolve().parents[1]


def fixture(image, variant):
    # Reuse the checked file-chain walker on a private copy whose PRG type is
    # temporarily presented as SEQ. The output retains the original PRG type.
    lookup = bytearray(image)
    directory = sector_offset(18, 1)
    entries = [directory + 2 + 32*n for n in range(8)]
    entries = [p for p in entries if image[p] == 0x82 and
               image[p+3:p+19].rstrip(b'\xa0') == b'SCHEDOVR']
    if len(entries) != 1:
        raise ValueError('expected one SCHEDOVR PRG')
    lookup[entries[0]] = 0x81
    _, offsets = dos_file(lookup, 'SCHEDOVR')
    payload = bytes(image[p] for p in offsets)
    if payload[:2] != b'\0\x12':
        raise ValueError('expected bank-1 $1200 payload')
    result = bytearray(image)
    for name, address, identity in (('iec', 0x1203, b'UIEC\0\1'),
                                    ('bootfs', 0xa000, b'UBFS\0\1')):
        index = 2 + address - 0x1200
        if payload[index:index+6] != identity:
            raise ValueError('invalid source identity '+name)
        if variant in (name, 'both'):
            result[offsets[index]] = ord('?')
    return bytes(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    image = args.disk.read_bytes()
    for variant in ('normal', 'iec', 'bootfs', 'both'):
        work = args.output/variant
        work.mkdir(parents=True, exist_ok=True)
        disk = work/'test.d64'
        disk.write_bytes(fixture(image, variant))
        port = choose_port()
        proc, master = launch_vice(disk, port, 'net.sf.VICE',
            ('-drive8truedrive', '-drive8type', '1541'))
        try:
            wait_for_byte(port, 0xf3e0, 2, time.monotonic()+210)
            flags, cells = capture_blocks(port, [
                (work/'flags.bin', 0xf065, 0xf066, 'kernel'),
                (work/'console.bin', console_address(), console_address()+0x557, 'kernel')])
            expected = bytes((variant not in ('iec', 'both'),
                              variant not in ('bootfs', 'both')))
            if flags != expected:
                raise AssertionError(f'{variant}: {flags.hex()} != {expected.hex()}')
            lines = [cells[i:i+64].decode('ascii', errors='replace').rstrip()
                     for i in range(0, 21*65, 65)]
            for n, label in enumerate(('IEC DRIVER HEADER ...', 'BOOTFS HEADER ...')):
                row = [s for s in lines if label in s]
                status = '[ OK ]' if expected[n] else '[ -- ]'
                if len(row) != 1 or not row[0].endswith(status):
                    raise AssertionError(variant+'\n'+'\n'.join(lines))
            records.append(dict(variant=variant, flags=flags.hex(), console='\n'.join(lines),
                                disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest()))
            print('PASS boot banner', variant, flags.hex(), flush=True)
        finally:
            terminate(proc, port)
            os.close(master)
    (args.output/'result.json').write_text(json.dumps(dict(
        source_sha256=hashlib.sha256(image).hexdigest(), runs=records), indent=2)+'\n')


if __name__ == '__main__':
    main()

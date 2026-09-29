#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the native IEC directory PRG against VICE's line-level drives.

This is an opt-in integration gate (`make iec-vice-probe`), not a host unit
test. VICE's Flatpak must be able to see the generated D64 in build/.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'build/bench/iec-directory'
PROGRAM = ARTIFACTS / 'iec-directory.prg'
DISK = ARTIFACTS / 'test.d64'
VICE = 'net.sf.VICE'


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def validate_directory(data: bytes) -> bytes:
    if len(data) != 0x200:
        raise ValueError('IEC result block is not 512 bytes')
    state, opened, terminal, closed, low, high = data[:6]
    length = low | (high << 8)
    if (state, opened, terminal, closed) != (2, 0, 1, 0):
        raise ValueError('directory open/read-EOI/close did not all succeed')
    if data[10] & 1 != 1 or data[11] & 1 != 0 or data[12] != data[10]:
        raise ValueError('IEC transaction did not select 1 MHz and restore speed')
    if data[13] != 0:
        raise ValueError('IEC bus output lines were not released after close')
    if data[14] != data[15]:
        raise ValueError('IEC transaction changed VIC bank selection')
    if not 64 <= length <= 256:
        raise ValueError(f'directory length {length} is invalid')
    stream = data[0x100:0x100 + length]
    if stream[:2] != b'\x01\x04' or not stream.endswith(b'\x00\x00\x00'):
        raise ValueError('directory has no expected load address or terminator')
    if b'\xd4\xc5\xd3\xd4\xd0\xd2\xcf\xc7' not in stream:
        raise ValueError('TESTPROG PETSCII file name was not received')
    if b'BLOCKS FREE.' not in stream:
        raise ValueError('directory footer was not received')
    return stream


def validate_no_device(data: bytes) -> None:
    if len(data) != 0x200 or data[:6] != b'\x80\x03\x00\x00\x00\x00':
        raise ValueError('absent device did not return NO_DEVICE cleanly')
    if data[10] != data[12] or data[13] != 0:
        raise ValueError('absent device did not restore speed and release bus')
    if data[14] != data[15]:
        raise ValueError('absent-device path changed VIC bank selection')


def capture(name: str, expected_state: int, *vice_args: str) -> bytes:
    result = ARTIFACTS / f'{name}.raw'
    command = [
        'python3', 'tools/vice_capture.py', str(PROGRAM), str(result),
        '--entry', '0x2800', '--raw-load', '--result-address', '0x3100',
        '--result-size', '0x200', '--state-offset', '0',
        '--complete-value', hex(expected_state), '--timeout', '60',
        '--poll-delay', '10', '--capture-incomplete', '--flatpak-id', VICE,
    ]
    command.extend(f'--vice-arg={arg}' for arg in vice_args)
    run(*command)
    return result.read_bytes()


def main() -> None:
    if not PROGRAM.is_file():
        raise SystemExit('run make iec-probe before iec-vice-probe')
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    # c1541 creates a fresh non-autoboot disk: attaching the ordinary UDEKS
    # disk would start its kernel before the monitor-loaded PRG can run.
    run('flatpak', 'run', '--command=c1541', VICE, '-format',
        'IEC TEST,01', 'd64', str(DISK))
    run('flatpak', 'run', '--command=c1541', VICE, '-attach', str(DISK),
        '-write', str(PROGRAM), 'TESTPROG')
    if DISK.stat().st_size != 174848:
        raise ValueError('c1541 did not create a standard 35-track D64')
    streams = []
    for drive in (1571, 1541):
        data = capture(f'vice-{drive}', 2, '-drive8truedrive',
                       '-drive8type', str(drive), '-8', str(DISK))
        streams.append(validate_directory(data))
    if streams[0] != streams[1]:
        raise ValueError('1571 and 1541 directory bytes differ')
    validate_no_device(capture('vice-no-device', 0x80,
                               '-drive8type', '0'))
    print(f'native IEC probe OK: {len(streams[0])} directory bytes on '
          '1571 and 1541; absent device returns NO_DEVICE')


if __name__ == '__main__':
    main()

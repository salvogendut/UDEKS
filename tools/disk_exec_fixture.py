#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Package disk-only UDEX launch fixtures without adding anything to bootfs."""
import argparse
from pathlib import Path
from build_d71 import install_prg_file
from build_udex import build_executable


def build_fixture(image: bytes, executable: bytes) -> bytes:
    if len(executable) < 17:
        raise ValueError('fixture needs a complete UDEX')
    if executable[6:10] != b'\x01\0\0\x02':
        raise ValueError('fixture must be ordinary 8502 UDEX at $0200')
    size = int.from_bytes(executable[10:12], 'little')
    bss = int.from_bytes(executable[12:14], 'little')
    if len(executable) != 16+size or size+bss > 0xa00:
        raise ValueError('fixture image/BSS does not fit APP1')
    expected = build_executable(executable[16:], cpu=1, load_address=0x200,
        entry_address=int.from_bytes(executable[14:16], 'little'), bss_size=bss)
    if executable != expected:
        raise ValueError('fixture has a noncanonical UDEX header')
    result = bytearray(image)
    install_prg_file(result, 'DISKCOW', executable, file_type=0x81)
    install_prg_file(result, 'BADUDEX', b'NOT A UDEX FILE\n', file_type=0x81)
    install_prg_file(result, 'SHORT', executable[:-1], file_type=0x81)
    # BRKs before the entry catch accidental invocation of the load address;
    # code checks all four BSS bytes before returning 37 (255 on failure).
    entry = bytes.fromhex('00 00 a2 00 bd 14 02 d0 08 e8 e0 04 90 f6 a9 25 60 a9 ff 60')
    install_prg_file(result, 'ENTRY', build_executable(entry, cpu=1,
        load_address=0x200, entry_address=0x202, bss_size=4), file_type=0x81)
    install_prg_file(result, 'LIMIT', build_executable(
        b'\xa9\x07\x60'+bytes(0xA00-3), cpu=1,
        load_address=0x200, entry_address=0x200), file_type=0x81)
    return bytes(result)


def negative_fixture(image: bytes, executable: bytes) -> bytes:
    """A separate mounted data disk exercises all UDEX rejection classes."""
    result = bytearray(image)
    for name, offset, value in (('MAGIC', 0, 0), ('VERSION', 4, 1),
                               ('CPU', 6, 2), ('FLAGS', 7, 2),
                               ('LOAD', 9, 3), ('ENTRY', 15, 1)):
        bad = bytearray(executable); bad[offset] = value
        install_prg_file(result, name, bad, file_type=0x81)
    install_prg_file(result, 'TRAIL', executable+b'x', file_type=0x81)
    install_prg_file(result, 'SIZE', build_executable(b'X'*0xA01, cpu=1,
        load_address=0x200, entry_address=0x200), file_type=0x81)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disk', type=Path)
    parser.add_argument('executable', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.resolve() in (args.disk.resolve(), args.executable.resolve()):
        parser.error('output must not overwrite either input')
    result = build_fixture(args.disk.read_bytes(), args.executable.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)


if __name__ == '__main__': main()

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

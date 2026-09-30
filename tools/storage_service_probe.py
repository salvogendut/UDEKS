#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold-boot qualification of the native storage service via the real CF30 gate.

The destructive debugger harness takes over a private VICE instance after boot
and graphics startup; it is not a shell-command acceptance test. All sessions
are terminated. No host-file device or KERNAL I/O calls service these requests.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

import shadow_boot_probe as sp
from build_d71 import install_prg_file
from capability_relocation_probe import inject_until_state
from vice_capture import choose_port, receive_prompts, monitor_command

ROOT = Path(__file__).resolve().parents[1]


def call(port, work, op, payload=b'', fd=0, count=None):
    request = bytearray(38)
    request[:14] = b'UTRQ\0\5' + bytes((1, op, 91, fd,
        len(payload) if count is None else count, 0, 0, 0))
    request[14:14+len(payload)] = payload
    # SEI / CLD / kernel page ownership / fresh hardware stack. The service
    # sees a transient C stack at $F7EF, precisely the dangerous overlay case.
    code = bytes.fromhex('78 d8 a2 ff 9a a9 00 8d 08 d5 8d 07 d5 8d 0a d5 '
        'a9 01 8d 09 d5 '
        'a9 5a a2 1d 95 02 ca 10 fb '
        'a9 a5 a2 ef 9d 00 f7 ca e0 ff d0 f8 '
        'a9 ef 85 06 a9 f7 85 07 20 30 cf '
        'a9 a5 8d f0 0b')
    stop = 0x0b00 + len(code)
    code += bytes((0x4c, stop & 255, stop >> 8))
    zp = bytearray([0x5a]*30)
    zp[4:6] = b'\xef\xf7'
    stack = bytes([0xa5]*0xf0)
    with socket.create_connection(('127.0.0.1', port), timeout=5) as conn:
        conn.settimeout(5)
        conn.sendall(b'm ff00 ff00\n')
        receive_prompts(conn, 2)
        for command in ('> ff01 00', '> 0bf0 00',
                        '> f359 '+request.hex(' '), '> 0b00 '+code.hex(' ')):
            conn.sendall((command+'\n').encode())
            receive_prompts(conn)
        conn.sendall(b'goto 0b00\n')
    try:
        sp.wait_for_byte(port, 0x0BF0, 0xA5, time.monotonic()+30)
    except TimeoutError:
        print(monitor_command(port, 'r').decode(errors='replace'), flush=True)
        sp.capture_blocks(port, [(work/'failure-common.bin', 0xf000, 0xffff, 'kernel'),
                                (work/'failure-module.bin', 0x1200, 0x1fff, 'worker'),
                                (work/'failure-state.bin', 0xe000, 0xe1ff, 'worker')])
        raise
    result, restored_zp, restored_stack = sp.capture_blocks(port, [
        (work/'request.bin', 0xF359, 0xF37E, 'kernel'),
        (work/'caller-zp.bin', 2, 0x1f, 'kernel'),
        (work/'caller-stack.bin', 0xf700, 0xf7ef, 'kernel')])
    if result[8] != 91:
        raise AssertionError('request sequence changed')
    if op in (17, 18) or payload.startswith(b'/mnt') or fd == 4:
        if restored_zp != zp or restored_stack != stack:
            raise AssertionError('storage gateway corrupted caller C context')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive', choices=('1541', '1571'), default='1541')
    parser.add_argument('--output', type=Path, default=ROOT/'build/storage/vice')
    parser.add_argument('--tiny-files', action='store_true',
        help='also reproduce the outstanding one-byte DOS stream EOF discrepancy (strict check)')
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    disk = work / ('native-storage' + args.disk.suffix)
    shutil.copyfile(args.disk, disk)
    samples = {'TWO': b'AB', 'EDGE': bytes(range(24)), 'BIN': bytes(range(256))*2+b'END'}
    if args.tiny_files: samples['ONE'] = b'\0'
    image = bytearray(disk.read_bytes())
    for name, data in samples.items():
        install_prg_file(image, name, data, file_type=0x81)
    disk.write_bytes(image)
    port = choose_port()
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
        ('-drive8truedrive', '-drive8type', args.drive))
    try:
        deadline = time.monotonic()+120
        sp.wait_for_byte(port, sp.ROOT_TERMINAL_STATUS_READY_ADDRESS, 2, deadline)
        print('native boot ready', flush=True)
        symbols = sp.symbol_addresses(ROOT/'build/8502/udeks-8502.map')
        inject_until_state(port, symbols, 'xinit', sp.VIC_STATUS_STATE_ADDRESS, 3, deadline)
        inject_until_state(port, symbols, 'xclock &', sp.XCLOCK_STATUS_STATE_ADDRESS, 3, deadline)
        print('xinit + xclock running before storage calls', flush=True)
        records = []
        def request(op, payload=b'', fd=0, count=None, error=0):
            result = call(port, work, op, payload, fd, count)
            records.append(result.hex())
            if result[12] != error or result[6] != (128 if error else 2):
                raise AssertionError(f'op {op}: {result.hex()} expected errno {error}')
            return result
        request(6, b'/mnt', 1, error=2)  # take over before snapshotting the clock
        before = sp.capture_blocks(port, [(work/'bitmap-before.bin', 0x6000, 0x7F3F, 'worker')])[0]
        # Drive 8 acknowledges ATN even for an absent address 11; the later
        # address-specific handshake times out (EIO), unlike an empty bus.
        request(17, b'\x0b/mnt', error=5)
        print('absent device rejected; retrying device 8', flush=True)
        request(17, b'\x08/mnt')
        if request(6, b'/mnt', 1)[11] != 4:
            raise AssertionError('wrong storage fd')
        request(18, b'/mnt', error=16)
        names = []
        for _ in range(32):
            result = request(7, fd=4, count=24)
            if result[11] == 0:
                break
            names.append(bytes(result[16:16+result[15]]).decode('ascii'))
        else:
            raise AssertionError('directory did not end')
        # Native boot data occupies raw sectors, not a directory UDEKS file.
        if not {'HELLO', 'SCHEDOVR'} <= set(names):
            raise AssertionError(f'native disk files missing: {names}')
        request(9, fd=4)
        request(6, b'/mnt/NOFILE', error=2)
        mismatches = []
        for name, expected in samples.items():
            request(6, b'/mnt/'+name.encode())
            request(1, fd=4, count=0)
            content = bytearray()
            for _ in range(32):
                result = request(1, fd=4, count=24)
                if not result[11]: break
                content.extend(result[14:14+result[11]])
            else:
                raise AssertionError('file never reached EOF')
            if content != expected:
                mismatches.append(f'{name}: expected {len(expected)} bytes, got {len(content)}: {content.hex()}')
            if request(1, fd=4, count=24)[11]:
                raise AssertionError('EOF is not repeatable')
            request(18, b'/mnt', error=16)
            request(9, fd=4)
            print(f'{name}: {len(content)} bytes, exact={content == expected}', flush=True)
        request(18, b'/mnt')
        request(6, b'/mnt', 1, error=2)
        # The same gate still reaches the original bootfs service.
        if request(6, b'/bin', 1)[11] != 3:
            raise AssertionError('bootfs fallback lost')
        if request(7, fd=3, count=24)[11] == 0:
            raise AssertionError('bootfs directory is empty')
        request(9, fd=3)
        after = sp.capture_blocks(port, [(work/'bitmap-after.bin', 0x6000, 0x7F3F, 'worker')])[0]
        if after != before:
            raise AssertionError('IEC service modified the VIC bitmap')
        if mismatches:
            raise AssertionError('\n'.join(mismatches))
        (work/'result.json').write_text(json.dumps({'drive': args.drive,
            'disk_sha256': hashlib.sha256(args.disk.read_bytes()).hexdigest(),
            'directory': names, 'requests': records, 'bitmap_unchanged': True,
            'exact_file_sizes': {name: len(data) for name, data in samples.items()}}, indent=2)+'\n')
        print(f'PASS: {names}; mount/list/unmount, bootfs fallback, bitmap intact', flush=True)
    finally:
        sp.terminate(proc, port)
        os.close(master)


if __name__ == '__main__':
    main()

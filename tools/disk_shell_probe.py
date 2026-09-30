#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prove disk-first shell boot and fallback by changing only the DOS USH file."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from disk_shell_fixture import build_fixture
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from storage_shell_probe import console_address
from vice_capture import choose_port, monitor_command

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive', choices=('1541', '1571'), default='1541')
    parser.add_argument('--output', type=Path, default=ROOT/'build/disk-shell/vice-1541')
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    queue = keyboard_queue_address((ROOT/'build/8502/udeks-8502.map').read_text(),
                                   (ROOT/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    results = []
    for variant, source, error, version in (('diskA', 1, 0, 'diskA'),
            ('diskB', 1, 0, 'diskB'), ('missing', 2, 11, '0.1.0'), ('bad', 2, 4, '0.1.0'),
            ('entry', 2, 10, '0.1.0'), ('flags', 2, 7, '0.1.0')):
        disk = work/(variant+args.disk.suffix)
        disk.write_bytes(build_fixture(args.disk.read_bytes(), variant))
        port = choose_port()
        proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
                                    ('-drive8truedrive', '-drive8type', args.drive))
        commands = []
        try:
            sp.wait_for_byte(port, 0xF3D9, 0xA5, time.monotonic()+180)
            status = sp.capture_blocks(port, [(work/(variant+'-boot.bin'), 0xF3DD, 0xF3DF, 'kernel')])[0]
            if status != bytes((source, error, 8)):
                raise AssertionError(f'{variant}: wrong boot source/error/device {status.hex()}')
            if source == 1:
                sp.wait_for_byte(port, 0xF3E0, 2, time.monotonic()+90)

            def command(text, expected, builtin=False):
                deadline = time.monotonic()+60
                sp.wait_for_byte(port, slots+1, 4, deadline)
                counter = 0xF3D8 if builtin else 0xF17E
                before = byte(port, counter)
                type_command(port, queue, text, deadline)
                sp.wait_for_byte(port, counter, (before+1)&255, deadline)
                sp.wait_for_byte(port, slots+1, 4, deadline)
                sp.wait_for_byte(port, slots+2, 2, deadline)
                cells = sp.capture_blocks(port, [(work/(variant+'-console.bin'), console_address(), console_address()+0x557, 'kernel')])[0]
                console = '\n'.join(cells[i:i+64].decode('ascii', errors='replace').rstrip()
                                    for i in range(0, 21*65, 65))
                if cells[-1] != 1 or expected not in console:
                    raise AssertionError(f'{variant} {text}: missing prompt/output {expected!r}\n{console}')
                if not builtin and (byte(port, 0xF285) != 3 or byte(port, 0xF287) != 0):
                    raise AssertionError(f'{variant} {text}: command failed')
                commands.append(dict(command=text, console=console))

            command('help', (version+'ery' if version.startswith('disk') else 'Recovery')+': mount umount', builtin=True)
            # Normal RC mounts device 8; recovery skips RC and stays unmounted.
            if source == 2: command('mount 8 /mnt', 'UDEKS:')
            command('cat /mnt/HELLO', 'HELLO UDEKS')
            command('umount /mnt', 'UDEKS:')
            command('echo recovered', 'recovered', builtin=True)
            results.append(dict(variant=variant, source=source, error=error,
                disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(), commands=commands))
            print(f'PASS {variant}: source={source}, error={error}, version={version}, startup/recovery mount policy, commands work', flush=True)
        except Exception:
            print(monitor_command(port, 'r').decode(errors='replace'), flush=True)
            print(monitor_command(port, 'm f280 f29f').decode(errors='replace'), flush=True)
            print(monitor_command(port, 'm f359 f3df').decode(errors='replace'), flush=True)
            raise
        finally:
            sp.terminate(proc, port)
            os.close(master)
    (work/'result.json').write_text(json.dumps(dict(drive=args.drive,
        disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(), runs=results), indent=2)+'\n')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold-boot disk utilities, mount-only recovery and graphics coexistence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port
from disk_shell_fixture import build_fixture

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    p.add_argument('--drive', choices=('1541', '1571'), default='1541')
    p.add_argument('--recovery', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); work = args.output.resolve(); work.mkdir(parents=True, exist_ok=True)
    disk = args.disk.resolve()
    if args.recovery:
        disk = work/('recovery'+disk.suffix)
        disk.write_bytes(build_fixture(args.disk.read_bytes(), 'missing'))
    queue = keyboard_queue_address((ROOT/'build/8502/udeks-8502.map').read_text(),
                                   (ROOT/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    port = choose_port(); records = []
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE', ('-drive8truedrive', '-drive8type', args.drive))
    try:
        sp.wait_for_byte(port, 0xF3D9, 0xA5, time.monotonic()+210)
        if byte(port, 0xF3DD) != (2 if args.recovery else 1): raise AssertionError('wrong shell source')
        if not args.recovery: sp.wait_for_byte(port, 0xF3E0, 2, time.monotonic()+90)
        def command(text, expected):
            deadline = time.monotonic()+90
            sp.wait_for_byte(port, slots+1, 4, deadline)
            before = byte(port, 0xF3D8)
            type_command(port, queue, text, deadline)
            sp.wait_for_byte(port, 0xF3D8, (before+1)&255, deadline)
            try:
                sp.wait_for_byte(port, slots+1, 4, deadline)
                sp.wait_for_byte(port, slots+2, 2, deadline)
            except TimeoutError:
                sp.capture_blocks(port, [(work/'failed-common.bin', 0xf000, 0xffff, 'kernel'),
                    (work/'failed-slots.bin', slots, slots+63, 'kernel'),
                    (work/'failed-console.bin', 0xc00, 0x1157, 'kernel'),
                    (work/'failed-ush.bin', 0x9000, 0x9fff, 'worker')])
                raise
            data = sp.capture_blocks(port, [(work/'console.bin', 0xc00, 0x1157, 'kernel')])[0]
            console = '\n'.join(data[i:i+64].decode('ascii', errors='replace').rstrip() for i in range(0, 21*65, 65))
            if data[-1] != 1 or any(item not in console for item in expected): raise AssertionError(text+'\n'+console)
            records.append(dict(command=text, console=console)); print('PASS', text, flush=True)
        if not args.recovery:
            command('cowsay mounted at boot', ('^__^', 'mounted at boot'))
            command('umount /mnt', ())
        command('cowsay unavailable', ('Unknown command: cowsay',))
        command('mount 8 /mnt', ())
        command('ls /bin', ('mount', 'umount', 'ush'))
        command('ls /mnt', ('COWSAY', 'DATE', 'LS', 'CAT', 'XCLOCK', 'XWAVE'))
        command('cowsay disk', ('^__^', 'disk'))
        command('/mnt/COWSAY explicit', ('^__^', 'explicit'))
        command('date 123456', ())
        command('date', ('12:34:',))
        command('/mnt/DATE 010203', ())
        command('date', ('01:02:',))
        command('cat /mnt/HELLO', ('HELLO UDEKS',))
        command('/mnt/CAT /mnt/HELLO', ('HELLO UDEKS',))
        command('/mnt/LS /bin', ('mount', 'umount', 'ush'))
        command('cat /mnt/NOFILE', ('cat: No such file or directory',))
        command('uname -a', ('UDEKS 0.1.0 c128 8502',))
        command('/mnt/LSHW', ('Video:', 'Expansion:'))
        command('lsmod', ('Modules:', 'resident'))
        command('lscpu', ('8502: resident executive', 'stock timing'))
        command('z80ctl status', ('State: ready', 'Transactions:'))
        command('z80ctl test', ('Z80 self-test: OK',))
        command('xinit nonsense', ('xinit [-q];',))
        command('xinit', ('VIC-II graphics active',))
        command('xclock &', ('xclock started &',))
        command('xwave &', ('xwave started &',))
        sp.wait_for_byte(port, 0xF27A, 21, time.monotonic()+90)
        command('cowsay together', ('together', '^__^'))
        command('ls /mnt', ('COWSAY', 'CAT'))
        command('cat /mnt/HELLO', ('HELLO UDEKS',))
        if byte(port, 0xf225) != 3 or byte(port, 0xf265) != 3: raise AssertionError('apps lost')
        command('z80ctl test', ('Z80 self-test: OK',))
        command('xwave -q', ('xwave stopped',))
        command('xclock -q', ('xclock stopped',))
        command('xinit -q', ('VIC-II graphics stopped',))
        command('xclock &', ('xclock started &',))
        command('xwave &', ('xwave started &',))
        command('umount /mnt', ())
        command('cowsay unavailable', ('Unknown command: cowsay',))
        command('echo recovery alive', ('recovery alive',))
        command('mount 8 /mnt', ())
        command('cowsay recovered', ('^__^', 'recovered'))
        if byte(port, 0xf11b): raise AssertionError('canary failure')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive, recovery=args.recovery,
            disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(), commands=records), indent=2)+'\n')
    finally:
        sp.terminate(proc, port); os.close(master)


if __name__ == '__main__': main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold boot and execute disk-only programs through normal ush keyboard input."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, monitor_command
from build_d71 import blank_d71, d64_compatibility_image
from disk_exec_fixture import negative_fixture

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/disk-exec/test.d64')
    parser.add_argument('--drive', choices=('1541', '1571'), default='1541')
    parser.add_argument('--output', type=Path, default=ROOT/'build/disk-exec/vice-1541')
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    port = choose_port()
    proc, master = sp.launch_vice(args.disk.resolve(), port, 'net.sf.VICE',
                                ('-drive8truedrive', '-drive8type', args.drive))
    records = []
    try:
        sp.wait_for_byte(port, 0xF155, 2, time.monotonic()+150)
        queue = keyboard_queue_address((ROOT/'build/8502/udeks-8502.map').read_text(),
                                       (ROOT/'build/8502/keyboard.s').read_text())
        slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']

        def command(text, error=0, exit_status=0, contains=(), launcher_owned=False):
            deadline = time.monotonic()+60
            sp.wait_for_byte(port, slots+1, 4, deadline)
            before = byte(port, 0xF17E)
            if error:
                sp.write_kernel_blocks(port, [(0xF17A, b'\x7f')])
            type_command(port, queue, text, deadline)
            if error:
                sp.wait_for_byte(port, 0xF17A, error, deadline)
            else:
                sp.wait_for_byte(port, 0xF17E, (before+1)&255, deadline)
            sp.wait_for_byte(port, slots+1, 4, deadline)
            sp.wait_for_byte(port, slots+2, 2, deadline)
            cells, status = sp.capture_blocks(port, [
                (work/'console.bin', 0x0C00, 0x1157, 'kernel'),
                (work/'loader.bin', 0xF280, 0xF29F, 'kernel')])
            console = '\n'.join(cells[i:i+64].decode('ascii', errors='replace').rstrip()
                                for i in range(0, 21*65, 65))
            if cells[-1] != 1:
                raise AssertionError(f'{text}: input cursor missing\n{console}')
            if not launcher_owned and error is not None and (status[6] != error or status[5] != (0x80|error if error else 3)):
                raise AssertionError(f'{text}: loader {status.hex()}\n{console}')
            if error == 0 and status[7] != exit_status:
                raise AssertionError(f'{text}: unexpected exit {status[7]}\n{console}')
            for item in contains:
                if item not in console:
                    raise AssertionError(f'{text}: missing {item!r}\n{console}')
            records.append(dict(command=text, loader=status.hex(), console=console))
            print('PASS', text, flush=True)

        command('/mnt/DISKCOW hi', error=11)
        command('mount 8 /mnt')
        command('ls /bin', contains=('mount', 'umount', 'ush'))
        command('/mnt/DISKCOW hello', contains=('hello', '^__^'))
        command('/mnt/DISKCOW again', contains=('again', '^__^'))
        command('/mnt/BADUDEX', error=4)
        command('/mnt/SHORT', error=9)
        command('/mnt/NOFILE', error=11)
        command('/mnt/DISKCOW recovered', contains=('recovered', '^__^'))
        command('/mnt/ENTRY', exit_status=37)
        command('/mnt/LIMIT', exit_status=7)
        command('cowsay disk', contains=('disk', '^__^'))
        command('cat /mnt/HELLO', contains=('HELLO UDEKS',))
        command('xinit', error=None, contains=('VIC-II graphics active',))
        command('xclock &', error=None)
        sp.wait_for_byte(port, 0xF225, 3, time.monotonic()+30)
        command('/mnt/DISKCOW graphics', contains=('graphics', '^__^'))
        command('xwave &', error=None)
        sp.wait_for_byte(port, 0xF27A, 21, time.monotonic()+45)
        command('/mnt/DISKCOW both', contains=('both', '^__^'))
        if byte(port, 0xF225) != 3 or byte(port, 0xF265) != 3:
            raise AssertionError('background applications lost')
        command('umount /mnt')
        command('/mnt/DISKCOW absent', error=11)
        command('mount 8 /mnt')
        command('/mnt/DISKCOW remount', contains=('remount', '^__^'))
        command('umount /mnt')
        negative = negative_fixture(blank_d71(), (ROOT/'build/user/cowsay.udx').read_bytes())
        bad_disk = work/('negative'+args.disk.suffix)
        bad_disk.write_bytes(d64_compatibility_image(negative)
                             if args.disk.suffix == '.d64' else negative)
        monitor_command(port, f'attach "{bad_disk}" 8')
        command('mount 8 /mnt')
        for name, error in (('MAGIC', 4), ('VERSION', 5), ('CPU', 6), ('FLAGS', 7),
                            ('LOAD', 8), ('ENTRY', 10), ('TRAIL', 9), ('SIZE', 9)):
            command('/mnt/'+name, error=error)
        command('umount /mnt')
        monitor_command(port, f'attach "{args.disk.resolve()}" 8')
        command('mount 8 /mnt')
        command('/mnt/DISKCOW final', contains=('final', '^__^'))
        # Fault-injected ownership, NOT a claim of creating/running a child:
        # STOPPED/ZOMBIE slots must protect the entire staging range and the
        # common launcher just as RUNNING does. Neither state is schedulable.
        protected = [(work/'owned-launcher.bin', 0xf280, 0xf29f, 'kernel'),
                     (work/'owned-slot.bin', 0x0200, 0x11ff, 'worker')]
        before = sp.capture_blocks(port, protected)
        for state in (5, 6):
            sp.write_kernel_blocks(port, [(slots+9, bytes((state,)))])
            command('/mnt/DISKCOW busy', error=3, launcher_owned=True,
                    contains=('task slot busy',))
            after = sp.capture_blocks(port, [(path.with_name('after-'+path.name), lo, hi, bank)
                                            for path, lo, hi, bank in protected])
            if after != before:
                raise AssertionError('rejected launch overwrote child storage or launcher')
        sp.write_kernel_blocks(port, [(slots+9, b'\0')])
        command('/mnt/DISKCOW released', contains=('released', '^__^'))
        monitor_command(port, 'detach 8')
        command('/mnt/DISKCOW removed', error=13)
        # Mount helper is the bootfs recovery program; cowsay now needs disk.
        command('umount /mnt')
        monitor_command(port, f'attach "{args.disk.resolve()}" 8')
        command('mount 8 /mnt')
        command('/mnt/DISKCOW restored', contains=('restored', '^__^'))
        monitor_command(port, f'screenshot "{work / "console.bmp"}" 0')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive,
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(), commands=records), indent=2)+'\n')
    except Exception:
        print(monitor_command(port, 'r').decode(errors='replace'), flush=True)
        print(monitor_command(port, 'm f280 f29f').decode(errors='replace'), flush=True)
        print(monitor_command(port, 'm f359 f37e').decode(errors='replace'), flush=True)
        sp.capture_blocks(port, [(work/'failure-console.bin', 0x0C00, 0x1157, 'kernel'),
                                (work/'failure-loader.bin', 0xf910, 0xfeff, 'kernel')])
        raise
    finally:
        sp.terminate(proc, port)
        os.close(master)


if __name__ == '__main__':
    main()

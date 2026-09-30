#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise mount/ls/cat/umount via the real ush path, without CPU takeover."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import time

import shadow_boot_probe as sp
from build_d71 import blank_d71, d64_compatibility_image, install_prg_file
from task_waitpid_probe import scheduler_symbols
from boot_staging_map import segment_bounds
from vice_capture import choose_port, monitor_command, parse_monitor_byte

ROOT = Path(__file__).resolve().parents[1]


def byte(port, address):
    return parse_monitor_byte(monitor_command(port, f'm {address:04x} {address:04x}'), address)


def keyboard_queue_address(map_text, assembly):
    """Resolve the test-only queue from this build, failing on layout drift."""
    module = re.search(r'^keyboard\.o:\n((?:[ \t].*\n)+)', map_text, re.M)
    offset = re.search(r'BSS\s+Offs=([0-9A-F]+)\s+Size=000047', module[1]) if module else None
    layout = re.search(r'\.segment\s+"BSS"\s+_event_queue:\s+\.res\s+64,\$00'
        r'\s+_queue_head:\s+\.res\s+1,\$00\s+_queue_tail:\s+\.res\s+1,\$00'
        r'\s+_queue_count:\s+\.res\s+1,\$00', assembly)
    if offset is None or layout is None:
        raise ValueError('keyboard queue layout changed')
    return segment_bounds(map_text, 'BSS')[0] + int(offset[1], 16)


def wait_keyboard_queue(port, queue, deadline):
    # This queue is bank-0 RAM, not common RAM. A plain monitor m can sample
    # bank 1 while a service is active and falsely report an empty queue.
    path = ROOT/'build/vice'/f'keyboard-queue-{port}.bin'
    path.parent.mkdir(parents=True, exist_ok=True)
    while time.monotonic() < deadline:
        if sp.capture_blocks(port, [(path, queue+66, queue+66, 'kernel')])[0] == b'\0':
            return
        time.sleep(0.01)
    raise TimeoutError('keyboard event queue did not drain')


def type_command(port, queue, text, deadline):
    # Use PRESS events, including Return, through the normal terminal/editor.
    # Submitted-record injection skips submit_line()'s newline and causes
    # silent commands to append a second prompt to the existing one.
    payload = text.encode('ascii') + b'\n'
    for start in range(0, len(payload), 16):
        batch = payload[start:start+16]
        wait_keyboard_queue(port, queue, deadline)
        events = b''.join(bytes((1, 1 if c == 10 else 0xff, c, 0)) for c in batch)
        sp.write_kernel_blocks(port, [(queue, events),
            (queue+64, bytes((len(batch) % 16, 0, len(batch))))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive', choices=('1541', '1571'), default='1541')
    parser.add_argument('--output', type=Path, default=ROOT/'build/storage/shell-1541')
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    disk = work / ('shell-test' + args.disk.suffix)
    shutil.copyfile(args.disk, disk)
    # Modify only our disposable disk, leaving the user's image untouched.
    # HELLO is already shipped in native images, in the native PETSCII alphabet.
    data = bytearray(disk.read_bytes())
    install_prg_file(data, 'TAIL', b'NO FINAL NEWLINE', file_type=0x81)
    install_prg_file(data, 'LONG', b'BLOCK OF FILE DATA\n'*40+b'END OF LONG FILE\n', file_type=0x81)
    install_prg_file(data, 'EMPTY', b'', file_type=0x81)
    install_prg_file(data, 'ONE', b'X', file_type=0x81)
    disk.write_bytes(data)
    # c1541 encodes uppercase host names in PETSCII's other letter range.
    subprocess.run(['flatpak', 'run', '--command=c1541', 'net.sf.VICE', '-attach', str(disk),
        '-write', str(ROOT/'bench/iec-directory/hello.txt'), 'ALT'],
        check=True, stdout=subprocess.DEVNULL)
    port = choose_port()
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
        ('-drive8truedrive', '-drive8type', args.drive))
    records = []
    try:
        sp.wait_for_byte(port, 0xF155, 2, time.monotonic()+150)
        queue = keyboard_queue_address((ROOT/'build/8502/udeks-8502.map').read_text(),
                                       (ROOT/'build/8502/keyboard.s').read_text())
        slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
        def command(text, expected_exit=None, contains=()):
            deadline = time.monotonic()+45
            sp.wait_for_byte(port, slots+1, 4, deadline)
            before = byte(port, 0xF17E)
            type_command(port, queue, text, deadline)
            sp.wait_for_byte(port, 0xF17E, (before+1)&255, deadline)
            try:
                sp.wait_for_byte(port, slots+1, 4, deadline)
                sp.wait_for_byte(port, slots+2, 2, deadline)
            except TimeoutError:
                print(monitor_command(port, 'r').decode(errors='replace'), flush=True)
                states = sp.capture_blocks(port, [
                    (work/'failure-tasks.bin', 0xc7d9, 0xceff, 'kernel'),
                    (work/'failure-status.bin', 0xf000, 0xf3ff, 'kernel'),
                    (work/'failure-storage.bin', 0xe000, 0xe1ff, 'worker'),
                    (work/'failure-console.bin', 0xc00, 0x1157, 'kernel')])
                print('task slots', states[0][:64].hex(), 'request', states[1][0x359:0x37f].hex(), flush=True)
                raise
            # Source/map-locked root-console cells: 21 rows, 65-byte stride.
            cells = sp.capture_blocks(port, [(work/'console.bin', 0x0C00, 0x1157, 'kernel')])[0]
            console = '\n'.join(cells[i:i+64].decode('ascii', errors='replace').rstrip()
                                for i in range(0, 21*65, 65))
            if cells[-1] != 1:
                raise AssertionError(f'{text}: input cursor did not return')
            if expected_exit is not None:
                if byte(port, 0xF285) != 3 or byte(port, 0xF287) != expected_exit:
                    raise AssertionError(f'{text}: unexpected loader/exit status\n{console}')
            for value in contains:
                if value not in console:
                    raise AssertionError(f'{text}: missing {value!r}\n{console}')
            records.append({'command': text, 'exit': expected_exit, 'console': console})
            print(f'PASS {text}', flush=True)
        command('ls /bin', 0, ('mount', 'umount', 'xclock', 'xwave'))
        command('mount 7 /mnt', 1, ('device 8-11',))
        command('mount 11 /mnt', 1, ('mount: failed',))
        command('ls /bin', 0)
        command('mount 8 /mnt', 0)
        command('ls /mnt', 0, ('SCHEDOVR', 'HELLO'))
        command('cat /mnt/HELLO', 0, ('HELLO UDEKS',))
        command('cat /mnt/ALT', 0, ('HELLO UDEKS',))
        command('cat /mnt/TAIL', 0, ('NO FINAL NEWLINE',))
        command('cat /mnt/EMPTY', 0)
        command('cat /mnt/ONE', 0)
        command('cat /mnt/LONG', 0, ('END OF LONG FILE',))
        command('cat /mnt/NOFILE', 1, ('cat: No such file or directory',))
        command('cat /mnt/HELLO', 0, ('HELLO UDEKS',))
        command('mount 8 /mnt', 1)
        command('umount /mnt', 0)
        command('ls /mnt', 1, ('ls: open failed',))
        command('mount 8 /mnt', 0)
        command('xinit', contains=('VIC-II graphics active',))
        command('xclock &')
        sp.wait_for_byte(port, 0xF225, 3, time.monotonic()+30)
        command('ls /mnt', 0, ('SCHEDOVR', 'HELLO'))
        command('xwave &')
        sp.wait_for_byte(port, 0xF27A, 21, time.monotonic()+45)
        command('ls /mnt', 0, ('HELLO',))
        command('cat /mnt/HELLO', 0, ('HELLO UDEKS',))
        command('umount /mnt', 0)
        command('ls /bin', 0, ('cowsay', 'date'))
        monitor_command(port, 'detach 8')
        command('mount 8 /mnt', 1)
        command('ls /bin', 0)
        replacement = blank_d71()
        install_prg_file(replacement, 'HELLO', b'SECOND DISK\n', file_type=0x81)
        new_disk = work/('replacement'+disk.suffix)
        new_disk.write_bytes(d64_compatibility_image(replacement)
                             if disk.suffix == '.d64' else replacement)
        monitor_command(port, f'attach "{new_disk}" 8')
        command('mount 8 /mnt', 0)
        command('cat /mnt/HELLO', 0, ('SECOND DISK',))
        command('umount /mnt', 0)
        monitor_command(port, f'attach "{disk}" 8')
        command('mount 8 /mnt', 0)
        command('cat /mnt/HELLO', 0, ('HELLO UDEKS',))
        command('umount /mnt', 0)
        if byte(port, 0xF225) != 3 or byte(port, 0xF265) != 3:
            raise AssertionError('background graphics app lost after storage commands')
        monitor_command(port, f'screenshot "{work / "console.bmp"}" 0')
        (work/'result.json').write_text(json.dumps({'drive': args.drive,
            'disk_sha256': hashlib.sha256(args.disk.read_bytes()).hexdigest(),
            'test_disk_sha256': hashlib.sha256(disk.read_bytes()).hexdigest(),
            'commands': records}, indent=2)+'\n')
        print('PASS interactive storage, input readiness, bootfs and background apps', flush=True)
    finally:
        sp.terminate(proc, port)
        os.close(master)


if __name__ == '__main__':
    main()

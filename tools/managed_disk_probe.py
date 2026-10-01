#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""True-drive cold boot, disk-only managed loads and atomic rejection checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from managed_app_fixture import dos_file, fixture, ERRORS
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from storage_shell_probe import console_address
from vice_capture import choose_port, monitor_command

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive', choices=('1541', '1571'), default='1541')
    parser.add_argument('--first', choices=('xclock', 'xwave'), default='xclock')
    parser.add_argument('--faults', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    work = args.output.resolve(); work.mkdir(parents=True, exist_ok=True)
    disk = args.disk.resolve(); image = disk.read_bytes()
    bootfs = (ROOT/'build/user/bootfs.img').read_bytes()
    names = [bootfs[24+n*24:40+n*24].split(b'\0')[0] for n in range(bootfs[6])]
    if b'xclock' in names or b'xwave' in names:
        raise AssertionError('normal bootfs still contains graphical apps')
    queue = keyboard_queue_address((ROOT/'build/8502/udeks-8502.map').read_text(),
                                   (ROOT/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    first, second = args.first, ('xwave' if args.first == 'xclock' else 'xclock')
    bases = {'xclock': 0x0200, 'xwave': 0x1200}
    states = {'xclock': 0xF225, 'xwave': 0xF265}
    programs = {name: bytes(image[p] for p in dos_file(image, name.upper())[1]) for name in bases}
    records = []
    port = choose_port()
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE', ('-drive8truedrive', '-drive8type', args.drive))
    try:
        sp.wait_for_byte(port, 0xF3E0, 2, time.monotonic()+210)

        def capture(tag, lo, size, bank='kernel'):
            return sp.capture_blocks(port, [(work/(tag+'.bin'), lo, lo+size-1, bank)])[0]

        def command(text, contains=None, loader_error=None):
            deadline = time.monotonic()+90
            sp.wait_for_byte(port, slots+1, 4, deadline)
            before = byte(port, 0xF3D8)
            type_command(port, queue, text, deadline)
            sp.wait_for_byte(port, 0xF3D8, (before+1)&255, deadline)
            sp.wait_for_byte(port, slots+1, 4, deadline)
            sp.wait_for_byte(port, slots+2, 2, deadline)
            cells = capture('console', console_address(), 0x558)
            console = '\n'.join(cells[i:i+64].decode('ascii', errors='replace').rstrip()
                                for i in range(0, 21*65, 65))
            if cells[-1] != 1 or (contains and contains not in console):
                raise AssertionError(text+'\n'+console)
            status = capture('loader', 0xF280, 32)
            if loader_error is not None and (status[6] != loader_error or status[5] != (0x80|loader_error if loader_error else 0)):
                raise AssertionError(text+': '+status.hex()+'\n'+console)
            records.append(dict(command=text, loader=status.hex(), console=console))
            print('PASS', text, flush=True)

        command('umount /mnt')  # Explicit setup for the missing-mount case.
        command('xinit', 'VIC-II graphics active')
        command(first+' -q', first+': not ready')
        command(first+' &', first+': not found; check /mnt', 11)
        command('mount 8 /mnt')
        command(first+' &', loader_error=0)
        sp.wait_for_byte(port, states[first], 3, time.monotonic()+30)
        command(first+' &', first+': already running')
        if first == 'xwave': sp.wait_for_byte(port, 0xF27A, 21, time.monotonic()+60)
        peer = capture('peer-before', bases[first], len(programs[first])-16)
        if peer != programs[first][16:]: raise AssertionError('loaded image differs from disk')
        target = capture('target-before', bases[second], 0xA00)
        if args.faults:
            monitor_command(port, 'detach 8')
            command(second+' &', second+': I/O error', 13)
            if capture('io-peer', bases[first], len(peer)) != peer or capture('io-target', bases[second], len(target)) != target:
                raise AssertionError('I/O failure mutated app slots')
            command('umount /mnt')
            monitor_command(port, f'attach "{disk}" 8')
            command('mount 8 /mnt')
            for variant, error in ERRORS.items():
                command('umount /mnt')
                bad = work/(variant+disk.suffix); bad.write_bytes(fixture(image, second.upper(), variant))
                monitor_command(port, f'attach "{bad}" 8')
                command('mount 8 /mnt')
                message = 'not found; check /mnt' if error == 11 else 'I/O error' if error == 13 else 'bad program'
                command(second+' &', second+': '+message, error)
                if capture('peer-after', bases[first], len(peer)) != peer or capture('target-after', bases[second], len(target)) != target:
                    raise AssertionError(variant+': rejected load mutated live slots')
                if byte(port, states[first]) != 3: raise AssertionError('peer stopped')
            command('umount /mnt')
            monitor_command(port, f'attach "{disk}" 8')
            command('mount 8 /mnt')
            # Deliberate ownership fault injection, not a scheduled-child test.
            launcher = capture('owned-launcher', 0xF280, 32)
            child = capture('owned-child', 0x0200, 0x1000, 'worker')
            for state in (5, 6):
                sp.write_kernel_blocks(port, [(slots+9, bytes((state,)))])
                command(second+' &', second+': slot busy')
                if capture('after-launcher', 0xF280, 32) != launcher or capture('after-child', 0x0200, 0x1000, 'worker') != child:
                    raise AssertionError('busy load overwrote child storage/launcher')
            sp.write_kernel_blocks(port, [(slots+9, b'\0')])
        command(second+' &', loader_error=0)
        sp.wait_for_byte(port, states[second], 3, time.monotonic()+30)
        sp.wait_for_byte(port, 0xF27A, 21, time.monotonic()+60)
        for name in bases:
            if capture(name+'-loaded', bases[name], len(programs[name])-16) != programs[name][16:]:
                raise AssertionError(name+': executable bytes changed')
        command('cowsay both', '^__^')
        command('umount /mnt')
        monitor_command(port, 'detach 8')
        for name in (second, first):
            command(name+' -q')
            sp.wait_for_byte(port, states[name], 2, time.monotonic()+30)
            command(name+' &')
            sp.wait_for_byte(port, states[name], 3, time.monotonic()+30)
        command('echo recovery alive', 'recovery alive')
        if byte(port, 0xF11B): raise AssertionError('lifecycle canary failure')
        (work/'result.json').write_text(json.dumps(dict(disk_sha256=hashlib.sha256(image).hexdigest(),
            first=first, drive=args.drive, faults=args.faults, bootfs_names=[n.decode() for n in names],
            code_matches_disk=True, retained_restart_without_media=True, commands=records), indent=2)+'\n')
    except Exception:
        print(monitor_command(port, 'r').decode(errors='replace'), flush=True)
        sp.capture_blocks(port, [(work/'failure-status.bin', 0xf110, 0xf3ef, 'kernel'),
                                (work/'failure-console.bin', console_address(), console_address()+0x557, 'kernel'),
                                (work/'failure-stack.bin', 0x0000, 0x01ff, 'kernel'),
                                (work/'failure-slots.bin', slots, slots+15, 'kernel')])
        raise
    finally:
        sp.terminate(proc, port); os.close(master)


if __name__ == '__main__': main()

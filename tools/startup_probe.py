#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold-boot RC and standalone FREE/DF through ush on true-drive VICE."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from build_d71 import sector_offset
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, monitor_command

ROOT = Path(__file__).resolve().parents[1]


def fixture(image, script):
    """Replace only the one-sector RC file (None removes its directory entry)."""
    image = bytearray(image)
    for slot in range(8):
        entry = sector_offset(18, 1)+2+32*slot
        if image[entry+3:entry+19].rstrip(b'\xa0') != b'RC': continue
        if script is None: image[entry] = 0
        else:
            if len(script) > 254: raise ValueError('fixture requires one sector')
            offset = sector_offset(image[entry+1], image[entry+2])
            if image[offset] != 0: raise ValueError('RC must occupy one sector')
            image[offset:offset+256] = bytes((0, len(script)+1))+script.ljust(254, b'\0')
        return bytes(image)
    raise ValueError('RC missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive', default='1541', choices=('1541', '1571'))
    parser.add_argument('--output', type=Path, default=ROOT/'build/startup/vice-1541')
    parser.add_argument('--variant', choices=('valid', 'invalid', 'missing', 'default'), default='valid')
    args = parser.parse_args()
    work = args.output.resolve(); work.mkdir(parents=True, exist_ok=True)
    image = args.disk.read_bytes()
    if args.variant != 'default':
        image = fixture(image, {'valid': b'# boot policy\r\n\necho RC-START\nmount 8 /mnt\nxinit\nxclock &\necho RC-END',
            'invalid': b'echo MUST-NOT-RUN\n\x01', 'missing': None}[args.variant])
    disk = work/('startup'+args.disk.suffix); disk.write_bytes(image)
    queue = keyboard_queue_address((ROOT/'build/8502/udeks-8502.map').read_text(),
                                   (ROOT/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    port = choose_port()
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE', ('-drive8truedrive', '-drive8type', args.drive))
    records = []
    try:
        sp.wait_for_byte(port, 0xF3E0, 2, time.monotonic()+210)
        sp.wait_for_byte(port, slots+1, 4, time.monotonic()+30)
        def console(name):
            cells = sp.capture_blocks(port, [(work/(name+'.bin'), 0x0C00, 0x1157, 'kernel')])[0]
            if cells[-1] != 1: raise AssertionError('input cursor missing')
            return '\n'.join(cells[i:i+64].decode('ascii', errors='replace').rstrip()
                             for i in range(0, 21*65, 65))
        boot = console('boot-console')
        if args.variant == 'valid':
            for item in ('RC-START', 'RC-END', 'VIC-II graphics active'):
                if item not in boot: raise AssertionError(boot)
            sp.wait_for_byte(port, 0xF225, 3, time.monotonic()+30)
        if args.variant == 'invalid' and ('MUST-NOT-RUN' in boot or 'RC failed' not in boot):
            raise AssertionError(boot)
        if args.variant in ('missing', 'default') and 'RC failed' in boot: raise AssertionError(boot)

        def command(text, expected=(), exit_status=0, builtin=False):
            deadline = time.monotonic()+90
            sp.wait_for_byte(port, slots+1, 4, deadline)
            counter = 0xF3D8 if builtin else 0xF17E
            before = byte(port, counter)
            type_command(port, queue, text, deadline)
            sp.wait_for_byte(port, counter, (before+1)&255, deadline)
            sp.wait_for_byte(port, slots+1, 4, deadline)
            sp.wait_for_byte(port, slots+2, 2, deadline)
            output = console('console')
            if any(item not in output for item in expected): raise AssertionError(text+'\n'+output)
            if not builtin and byte(port, 0xF287) != exit_status: raise AssertionError('exit status: '+text+'\n'+output)
            records.append(dict(command=text, console=output))
            print('PASS', text, flush=True)

        if args.variant in ('missing', 'invalid'): command('mount 8 /mnt')
        if args.variant == 'default':
            if 'mount: failed' in boot: raise AssertionError(boot)
            if 'mount: /mnt ready (read-only)' not in boot: raise AssertionError(boot)
            command('xclock &', ('xclock started &',), builtin=True)
            sp.wait_for_byte(port, 0xF225, 3, time.monotonic()+30)
            command('xwave &', ('xwave started &',), builtin=True)
            sp.wait_for_byte(port, 0xF265, 3, time.monotonic()+30)
        command('free', ('total 2560  used 0  free 2560', 'not total unused physical RAM'))
        # An independent expectation from the disk's primary BAM.
        bam = image[sector_offset(18, 0):sector_offset(18, 0)+256]
        total = 1328 if bam[3] & 128 else 664
        available = sum(bam[4*t] for t in range(1, 36) if t != 18)
        if bam[3] & 128: available += sum(bam[220+t] for t in range(1, 36) if t != 18)
        command('df', (f'{total}         {total-available}   {available}', 'Read-only mount'))
        command('/mnt/DF /mnt', (f'{total}         {total-available}   {available}',))
        command('df /bad', ('usage: df [/mnt]',), 1)
        command('cat /mnt/HELLO', ('HELLO UDEKS',))
        command('ls /mnt', ('FREE', 'DF', 'USH'))
        if args.variant == 'default':
            command('xwave -q', ('xwave stopped',), builtin=True)
            command('xclock -q', ('xclock stopped',), builtin=True)
        command('umount /mnt')
        command('echo recovery OK', ('recovery OK',), builtin=True)
        command('help', ('Recovery: mount umount',), builtin=True)
        driver = (ROOT/'build/storage/driver.bin').read_bytes()
        # Driver is code only. A shell-stack overrun into it is observable.
        live = sp.capture_blocks(port, [(work/'driver-after.bin', 0xE300, 0xE300+len(driver)-1, 'worker')])[0]
        if live != driver: raise AssertionError('IEC code below the shell stack changed')
        monitor_command(port, f'screenshot "{work / "console.bmp"}" 0')
        (work/'result.json').write_text(json.dumps(dict(variant=args.variant, drive=args.drive,
            disk_sha256=hashlib.sha256(image).hexdigest(), total=total, free=available,
            boot_console=boot, driver_intact=True, commands=records), indent=2)+'\n')
        print('PASS startup', args.variant, 'driver intact, df', available, '/', total, flush=True)
    except Exception:
        print(monitor_command(port, 'r').decode(errors='replace'), flush=True)
        sp.capture_blocks(port, [(work/'failure-console.bin', 0x0C00, 0x1157, 'kernel'),
                                (work/'failure-status.bin', 0xF110, 0xF3EF, 'kernel')])
        raise
    finally:
        sp.terminate(proc, port); os.close(master)


if __name__ == '__main__': main()

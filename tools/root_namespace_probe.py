#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold-boot system-root + independent device-9 acceptance, through real ush."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from build_d71 import blank_d71, d64_compatibility_image, install_prg_file
from disk_shell_fixture import build_fixture
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from boot_staging_map import segment_bounds
from vice_capture import choose_port, monitor_command

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive', choices=('1541', '1571'), default='1541')
    parser.add_argument('--output', type=Path, default=ROOT/'build/root-namespace/vice-1541')
    parser.add_argument('--recovery', action='store_true')
    args = parser.parse_args()
    work = args.output.resolve(); work.mkdir(parents=True, exist_ok=True)
    image = args.disk.read_bytes()
    if args.recovery: image = build_fixture(image, 'missing')
    disk = work/('system'+args.disk.suffix); disk.write_bytes(image)
    data = blank_d71()
    install_prg_file(data, 'HELLO', b'DEVICE NINE DATA\n', file_type=0x81)
    install_prg_file(data, 'RECOVER', (ROOT/'build/user/cowsay.udx').read_bytes(), file_type=0x81)
    data_disk = work/'data.d64'; data_disk.write_bytes(d64_compatibility_image(data))
    queue = keyboard_queue_address((ROOT/'build/8502/udeks-8502.map').read_text(),
                                   (ROOT/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    console_base = segment_bounds((ROOT/'build/8502/udeks-8502.map').read_text(), 'LOWBSS')[0]
    port = choose_port()
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
        ('-drive8truedrive', '-drive8type', args.drive,
         '-drive9truedrive', '-drive9type', '1541', '-9', str(data_disk)))
    records = []
    try:
        sp.wait_for_byte(port, 0xF3D9, 0xA5, time.monotonic()+240)
        sp.wait_for_byte(port, 0xF3DD, 2 if args.recovery else 1, time.monotonic()+10)
        if not args.recovery: sp.wait_for_byte(port, 0xF3E0, 2, time.monotonic()+90)

        def console(name):
            cells = sp.capture_blocks(port, [(work/(name+'.bin'), console_base, console_base+0x557, 'kernel')])[0]
            if cells[-1] != 1: raise AssertionError('input cursor missing')
            return '\n'.join(cells[i:i+64].decode('ascii', errors='replace').rstrip()
                             for i in range(0, 21*65, 65))

        boot = console('boot-console')
        if 'RC failed' in boot or 'mount: failed' in boot: raise AssertionError(boot)
        print('PASS cold boot', 'recovery' if args.recovery else 'disk root', flush=True)

        def command(text, expected=(), status=0, builtin=False):
            began = time.monotonic(); deadline = began+150
            sp.wait_for_byte(port, slots+1, 4, deadline)
            counter = 0xF3D8 if builtin else 0xF17E
            before = byte(port, counter)
            type_command(port, queue, text, deadline)
            sp.wait_for_byte(port, counter, (before+1)&255, deadline)
            sp.wait_for_byte(port, slots+1, 4, deadline)
            sp.wait_for_byte(port, slots+2, 2, deadline)
            output = console('console')
            if any(item not in output for item in expected): raise AssertionError(text+'\n'+output)
            if not builtin and byte(port, 0xF287) != status:
                raise AssertionError('exit status: '+text+'\n'+output)
            records.append(dict(command=text, console=output, seconds=time.monotonic()-began))
            print('PASS', text, flush=True)

        command('pwd', ('/\n',), builtin=True)
        if not args.recovery:
            command('df', ('iec8', 'Mounted on'))
            command('df /mnt', ('not mounted',), 1)
            command('ls /', ('bin\netc\nmnt', 'hello'))
            command('ls /bin', ('ush', 'cowsay', 'mount', 'umount'))
            command('cd etc', builtin=True)
            command('pwd', ('/etc\n',), builtin=True)
            command('ls', ('rc\n',))
            command('cat rc', ('Device 8 is already the system root',))
            command('cd ../bin', builtin=True)
            command('pwd', ('/bin\n',), builtin=True)
            command('./cowsay root-path', ('root-path',))
            command('cd /', builtin=True)
            command('cat /hello', ('HELLO UDEKS',))
            command('cat /NOFILE', ('No such file or directory',), 1)
        command('mount 9 /mnt', ('mount: /mnt ready',))
        if args.recovery:
            command('/mnt/RECOVER recovery', ('recovery',))
        else:
            command('df /mnt', ('iec9', '/mnt'))
            command('cat /mnt/HELLO', ('DEVICE NINE DATA',))
            command('cd /mnt', builtin=True)
            command('pwd', ('/mnt\n',), builtin=True)
            command('ls', ('HELLO', 'RECOVER'))
            command('cat HELLO', ('DEVICE NINE DATA',))
            command('umount /mnt', ('mount: failed',), 1)
            command('cd ..', builtin=True)
        command('umount /mnt')
        if not args.recovery:
            command('df', ('iec8',))
            command('cowsay system-still-here', ('system-still-here',))
            command('xclock &', ('xclock started &',), builtin=True)
            sp.wait_for_byte(port, 0xF225, 3, time.monotonic()+90)
            command('xwave &', ('xwave started &',), builtin=True)
            sp.wait_for_byte(port, 0xF265, 3, time.monotonic()+90)
            command('cat /etc/rc', ('Device 8 is already the system root',))
            command('xwave -q', ('xwave stopped',), builtin=True)
            command('xclock -q', ('xclock stopped',), builtin=True)
        command('echo namespace-ok', ('namespace-ok',), builtin=True)
        driver = (ROOT/'build/storage/driver.bin').read_bytes()
        live = sp.capture_blocks(port, [(work/'driver-after.bin', 0xE300, 0xE300+len(driver)-1, 'worker')])[0]
        if live != driver: raise AssertionError('shell stack corrupted IEC driver')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive, recovery=args.recovery,
            disk_sha256=hashlib.sha256(image).hexdigest(), data_sha256=hashlib.sha256(data_disk.read_bytes()).hexdigest(),
            boot_console=boot, driver_intact=True, commands=records), indent=2)+'\n')
        monitor_command(port, f'screenshot "{work / "console.bmp"}" 0')
    except Exception:
        print(monitor_command(port, 'r').decode(errors='replace'), flush=True)
        sp.capture_blocks(port, [(work/'failure-console.bin', console_base, console_base+0x557, 'kernel'),
                                (work/'failure-status.bin', 0xF110, 0xF3EF, 'kernel'),
                                (work/'failure-storage.bin', 0xE000, 0xE1FF, 'worker')])
        raise
    finally:
        sp.terminate(proc, port); os.close(master)


if __name__ == '__main__': main()

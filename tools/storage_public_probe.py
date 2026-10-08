#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Public disk commands, binary readback and reboot persistence on a fresh copy.

The source disk is never attached or modified. No syscall/service patches;
commands enter via the keyboard queue and the ordinary shell/loader/SDK.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import build_d81 as d81
from build_d71 import sector_offset
from build_scheduler_overlay import map_segments
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, monitor_command

ROOT = Path(__file__).resolve().parents[1]


def files(image):
    offset, start = (d81.sector_offset, (40, 3)) if len(image) == d81.SIZE else (sector_offset, (18, 1))
    result = {}
    for entry in d81.entries(image, offset, *start):
        if entry[0] not in (0x81, 0x82):
            raise AssertionError('unclosed or unsupported file')
        name = bytes(c-128 if 193 <= c <= 218 else c for c in entry[3:19].rstrip(b'\xa0'))
        if name in result: raise AssertionError('folded duplicate filename')
        result[name] = d81.file_bytes(image, entry, offset)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive', choices=('1541', '1571', '1581'), default='1541')
    parser.add_argument('--output', type=Path, default=ROOT/'build/storage/public')
    parser.add_argument('--mutations', action='store_true', help='qualify cp/mv/rm on the disposable copy')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='public-'+args.drive+'-', dir=args.output.resolve()))
    original = args.disk.read_bytes()
    before_files = files(original)
    disk = work/('disposable'+args.disk.suffix)
    disk.write_bytes(original)
    text = (ROOT/'build/8502/udeks-8502.map').read_text()
    segments = map_segments(text)
    queue = keyboard_queue_address(text, (ROOT/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    records = []
    for boot in range(2):
        port = choose_port()
        proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
            ('-console', '-jamaction', '5', '-drive8truedrive', '-drive8type', args.drive),
            log_path=work/('vice-'+str(boot)+'.log'))

        def capture(tag, address, size):
            return sp.capture_blocks(port, [(work/(tag+'.bin'), address, address+size-1, 'kernel')])[0]

        def prompt():
            deadline = time.monotonic()+120
            while True:
                state = capture('prompt', slots+1, 2)
                if state == b'\4\2': return
                if time.monotonic() > deadline: raise TimeoutError(('shell prompt', state.hex()))
                time.sleep(.05)

        def console():
            cells = capture('console', segments['LOWBSS'][0], 0x558)
            return '\n'.join(cells[i:i+64].decode('ascii', errors='replace').rstrip()
                             for i in range(0, 1365, 65))

        def command(line, contains='', status=0):
            prompt()
            previous = byte(port, 0xf3d8)
            type_command(port, queue, line, time.monotonic()+120)
            sp.wait_for_byte(port, 0xf3d8, (previous+1)&255, time.monotonic()+120)
            prompt()
            output = console()
            if contains not in output: raise AssertionError((line, output))
            if status is not None and byte(port, 0xf287) != status:
                raise AssertionError((line, 'exit', byte(port, 0xf287), output))
            records.append(dict(boot=boot, command=line, console=output, status=status))
            print('PASS', boot, line, flush=True)

        try:
            sp.wait_for_byte(port, 0xf3e0, 2, time.monotonic()+240)
            if args.mutations:
                if boot == 0:
                    command('cp /NOFILE /MISSING', 'No such file or directory', 1)
                    command('cp /hello /COPY')
                    command('cat /COPY', 'HELLO UDEKS')
                    command('cp /hello /COPY', 'File exists', 1)
                    command('mv /COPY /RENAMED')
                    command('cat /RENAMED', 'HELLO UDEKS')
                    command('rm /RENAMED')
                    command('cat /RENAMED', 'No such file or directory', 1)
                    command('save /EMPTY 0', 'created and verified')
                    command('cp /EMPTY /EMPTY2')
                    command('save -c /EMPTY2 0', 'save: verified')
                    command('rm /EMPTY')
                    command('rm /EMPTY2')
                    size = 2048 if args.drive == '1541' else 4096
                    command(f'save /BINARY {size}', 'created and verified')
                    command('xclock &', status=None)
                    command('cp /BINARY /BINCP')
                    command(f'save -c /BINCP {size}', 'save: verified')
                    command('mv /BINCP /BINMOVE')
                    command(f'save -c /BINMOVE {size}', 'save: verified')
                    command('rm /BINARY')
                    command('rm /BINMOVE')
                    command('xclock -q', status=None)
                    command('mount -o remount,ro 8 /', 'ready (read-only)')
                    for line in ('cp /hello /RO', 'mv /hello /RO', 'rm /hello'):
                        command(line, 'Read-only filesystem', 1)
                    command('mount -o remount,rw 8 /', 'ready (read-write)')
                    command('cp /hello /PERSIST')
                else:
                    command('cat /PERSIST', 'HELLO UDEKS')
                    command('rm /PERSIST')
                    command('cat /hello', 'HELLO UDEKS')
                if byte(port, 0xf11b): raise AssertionError('task canary failure')
                continue
            command('df', 'Read-write mount')
            if boot == 0:
                command('save /BOOTRW 24', 'created and verified')
            else:
                command('save -c /BOOTRW 24', 'save: verified')
            command('mount -o remount,ro 8 /', 'ready (read-only)')
            command('save /NOWRITE 1', 'Read-only filesystem', 1)
            command('df', 'Read-only mount')
            if boot == 0:
                command('mount -o remount,rw 8 /', 'ready (read-write)')
                command('df', 'Read-write mount')
                for name, size in (('WRTEST', 515), ('EMPTY', 0), ('ONE', 1), ('EXACT', 254)):
                    command(f'save /{name} {size}', 'save: created and verified')
                command('save /wrtest 515', 'File exists', 1)
                # Root masks reserved suffixes; callers use /bin instead.
                command('save /bad.BIN 1', 'No such file or directory', 1)
                command('save /bin/new 1', 'Invalid or unsupported request', 1)
                command('mount 8 /mnt', 'Device or resource busy', 1)
                command('xclock &', status=None)
                sp.wait_for_byte(port, 0xf246, 1, time.monotonic()+120)
                command('save /LIVE 24', 'save: created and verified')
                command('cat /hello', 'HELLO UDEKS')
                command('xclock -q', status=None)
                sp.wait_for_byte(port, 0xf246, 0, time.monotonic()+120)
                command('mount -o remount,ro 8 /', 'ready (read-only)')
                command('save /NOWRITE 1', 'Read-only filesystem', 1)
                command('df -h', 'Read-only mount')
            else:
                for name, size in (('WRTEST', 515), ('EMPTY', 0), ('ONE', 1), ('EXACT', 254), ('LIVE', 24)):
                    command(f'save -c /{name} {size}', 'save: verified')
                command('cat /hello', 'HELLO UDEKS')
            if byte(port, 0xf11b): raise AssertionError('task canary failure')
        except Exception:
            print(console(), flush=True)
            print(monitor_command(port, 'r').decode(errors='replace'), flush=True)
            capture('failure-request', 0xf359, 38)
            capture('failure-tasks', slots, 64)
            sp.capture_blocks(port, [(work/'failure-storage.bin', 0xe000, 0xe17f, 'worker')])
            raise
        finally:
            sp.terminate(proc, port)
            os.close(master)
    after_files = files(disk.read_bytes())
    for name, data in before_files.items():
        if after_files.get(name) != data: raise AssertionError(('existing file changed', name))
    expected = {name.encode(): bytes(i&255 for i in range(size)) for name, size in
                (('BOOTRW', 24), ('WRTEST', 515), ('EMPTY', 0), ('ONE', 1), ('EXACT', 254), ('LIVE', 24))}
    if args.mutations: expected = {}
    if {n: d for n, d in after_files.items() if n not in before_files} != expected:
        raise AssertionError('created files disagree with exact binary patterns')
    if args.disk.read_bytes() != original: raise AssertionError('source image changed')
    result = dict(drive=args.drive, disk_sha256=hashlib.sha256(original).hexdigest(),
                  written_disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),
                  original_files_unchanged=len(before_files),
                  created={n.decode(): len(d) for n, d in expected.items()}, checks=records)
    (work/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS public writes, reboot readback and existing-file preservation:', work, flush=True)


if __name__ == '__main__': main()

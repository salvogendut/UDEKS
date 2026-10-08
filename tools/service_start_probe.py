#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold boot/date/xclock and retired-startup re-entry on a disposable VICE disk.

This qualifies only the production one-shot guard, NOT disk module loading.
Commands use the ordinary shell keyboard-event path. The final re-entry test
deliberately damages SREG and the old startup instructions in a paused monitor
session, then uses a dead boot-page trampoline and ends the emulator session.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from build_scheduler_overlay import map_segments
from capability_relocation_probe import install_and_resume
from gen_capability_imports import map_exports
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port

ROOT = Path(__file__).resolve().parents[1]


def retirement_trampoline(entry, retired):
    """Poison and call atomically, with no registry poll between the two.

    Clearing diagnostics in a monitor session then resuming before JSR is
    racy: ordinary poll_all legitimately updates SREG even without startup.
    This disposable final probe deliberately never returns to the OS.
    """
    code = bytearray.fromhex('78 d8 a9 00 a2 17 9d 90 f0 ca 10 fa a9 02 8d')
    code += retired.to_bytes(2, 'little')
    code += b'\x20' + entry.to_bytes(2, 'little')
    code += bytes.fromhex('8d 20 0b a9 a5 8d 21 0b')
    spin = 0x0b00+len(code)
    code += b'\x4c' + spin.to_bytes(2, 'little')
    return code.ljust(0x20, b'\0') + b'\xff\0'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d71')
    parser.add_argument('--drive', choices=('1541', '1571', '1581'), default='1571')
    parser.add_argument('--output', type=Path, default=ROOT/'build/services/time/vice')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='startup-', dir=args.output.resolve()))
    disk = work/('disposable'+args.disk.suffix)
    original = args.disk.read_bytes()
    disk.write_bytes(original)
    map_text = (ROOT/'build/8502/udeks-8502.map').read_text()
    layout, exports = map_segments(map_text), map_exports(map_text)
    entry = exports['_udeks_service_start_all'][0]
    retired = exports['_udeks_service_start_all_once'][0]
    queue = keyboard_queue_address(map_text, (ROOT/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    records = []
    port = choose_port()
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
        ('-console', '-jamaction', '5', '-drive8truedrive', '-drive8type', args.drive),
        log_path=work/'vice.log')

    def capture(tag, address, size):
        path = work/(tag+'.bin')
        raw = sp.capture_blocks(port, [(path, address, address+size-1, 'kernel')])[0]
        path.write_bytes(raw)
        return raw

    def prompt():
        deadline = time.monotonic()+120
        while time.monotonic() < deadline:
            if capture('prompt', slots+1, 2) == b'\4\2':
                return
            time.sleep(.05)
        raise TimeoutError('shell prompt')

    def command(line, contains=''):
        prompt()
        previous = byte(port, 0xf3d8)
        type_command(port, queue, line, time.monotonic()+120)
        sp.wait_for_byte(port, 0xf3d8, (previous+1)&255, time.monotonic()+120)
        prompt()
        cells = capture('console', layout['LOWBSS'][0], 0x558)
        output = '\n'.join(cells[i:i+64].decode('ascii', errors='replace').rstrip()
                           for i in range(0, 1365, 65))
        if contains not in output:
            raise AssertionError((line, output))
        if byte(port, 0xf287):
            raise AssertionError((line, 'nonzero command exit', output))
        records.append(dict(command=line, console=output))
        print('PASS', line, flush=True)

    try:
        sp.wait_for_byte(port, 0xf3e0, 2, time.monotonic()+240)
        prompt()
        registry = capture('registry-before', 0xf090, 24)
        if registry[:6] != b'SREG\1\2':
            raise AssertionError('service startup did not complete')
        command('date -s 12:34:00')
        command('date', '12:34:')
        command('xclock &')
        sp.wait_for_byte(port, 0xf246, 1, time.monotonic()+120)
        command('cat /hello', 'HELLO UDEKS')
        command('xclock -q')
        sp.wait_for_byte(port, 0xf246, 0, time.monotonic()+120)
        if byte(port, 0xf11b):
            raise AssertionError('task canary failure')
        # Stop the first-entry routine from being executable. A second startup
        # would JAM immediately, rather than silently drawing a new console.
        install_and_resume(port, 0x0b00, retirement_trampoline(entry, retired))
        sp.wait_for_byte(port, 0x0b21, 0xa5, time.monotonic()+30)
        sp.wait_for_byte(port, 0x0b20, 0, time.monotonic()+30)
        registry = capture('registry-after-reentry', 0xf090, 24)
        if any(registry):
            raise AssertionError('retired startup rewrote SREG')
        result = dict(scope='production startup guard; module is NOT installed',
                      disk_sha256=hashlib.sha256(original).hexdigest(),
                      drive=args.drive, commands=records,
                      reentry='zero result after SREG corruption and retired-entry JAM poison')
        (work/'report.json').write_text(json.dumps(result, indent=2)+'\n')
        print('PASS retired startup guard; evidence:', work, flush=True)
    finally:
        sp.terminate(proc, port)
        os.close(master)
    if args.disk.read_bytes() != original:
        raise AssertionError('source disk changed')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Background argv and prompt-safe byte-stream output through real task gates.

Cold boots disposable media. Only keyboard events are injected; all launches,
WRITEs, waits, reads, cancellation and exits execute normally. No timing claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from add_disk_apps import add_apps
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_app_layout import ALLOCATIONS
from o65_to_udex import relocate_executable
from storage_shell_probe import sp, keyboard_queue_address, type_command, wait_keyboard_queue
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('d64', 'd71', 'd81'), default='d81')
    args = parser.parse_args()
    out = ROOT/'build/native-console/jobs'; out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=args.format+'-', dir=out))
    source = (ROOT/f'build/boot/udeks.{args.format}').read_bytes()
    # Keep normal D64 content intact: two demos fit its remaining blocks.
    # D71/D81 additionally carry the silent READ-denial peer.
    names = ('ASK', 'TICKER') if args.format == 'd64' else ('ASK', 'BGREAD', 'TICKER')
    apps = {n: (ROOT/f'build/native-console/{n.lower()}/{n}.BIN').read_bytes() for n in names}
    fixture = add_apps(source, [(n+'.BIN', d) for n, d in apps.items()])
    disk = work/('test.'+args.format); disk.write_bytes(fixture)
    text = (ROOT/'build/8502/udeks-8502.map').read_text()
    seg = map_segments(text)
    queue = keyboard_queue_address(text, (ROOT/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    symbols = {n: map_exports((ROOT/f'build/native-console/{n.lower()}/program.map').read_text()) for n in apps}
    port = choose_port(); records = []
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
        ('-console', '-jamaction', '5', '-drive8truedrive', '-drive8type',
         dict(d64='1541', d71='1571', d81='1581')[args.format]), log_path=work/'vice.log')

    def capture(tag, address, size, bank='kernel'):
        return sp.capture_blocks(port, [(work/(tag+'.bin'), address, address+size-1, bank)])[0]

    def byte(address):
        return capture('byte-'+hex(address), address, 1)[0]

    def screen(tag='console'):
        data = capture(tag, seg['LOWBSS'][0], 1368)
        return '\n'.join(data[i:i+64].decode('ascii', errors='replace').rstrip()
                         for i in range(0, 1365, 65))

    def wait(test, label, seconds=120):
        deadline = time.monotonic()+seconds
        while not test():
            if time.monotonic() > deadline: raise AssertionError((label, screen()))
            time.sleep(.05)

    def blocked(task):
        return capture('slot-'+str(task), slots+(task-1)*8, 8)[1:3] == b'\4\2'

    def prompt():
        wait(lambda: blocked(1), 'shell prompt')

    def command(line, foreground=False):
        prompt(); before = byte(0xf3d8)
        type_command(port, queue, line, time.monotonic()+120)
        wait(lambda: byte(0xf3d8) == (before+1) & 255, 'command consumed')
        if not foreground: prompt()

    def events(text=None, scan=None):
        rows = [bytes((1, scan, 0, 0))] if scan is not None else [bytes((1, 255, ch, 0)) for ch in text]
        for start in range(0, len(rows), 16):
            batch = rows[start:start+16]
            wait_keyboard_queue(port, queue, time.monotonic()+30)
            sp.write_kernel_blocks(port, [(queue, b''.join(batch)),
                (queue+64, bytes((len(batch) % 16, 0, len(batch))))])
        wait_keyboard_queue(port, queue, time.monotonic()+30)

    def private(app, task, name, size=1):
        base = next(row[1] for row in ALLOCATIONS if row[0] == task)
        return capture(app+'-'+str(task)+'-'+name, symbols[app]['_'+name][0]-0x1000+base, size, 'worker')

    def started(task):
        wait(lambda: 1 <= private('TICKER', task, 'ticker_step')[0] <= 5, 'background ticker started')

    def finished(task, argv, tag):
        wait(lambda: private('TICKER', task, 'ticker_step') == b'\6', 'ticker finished')
        wait(lambda: byte(slots+(task-1)*8+1) == 0, 'background reaped')
        if private('TICKER', task, 'ticker_failure') != b'\0': raise AssertionError('ticker failed')
        block = private('TICKER', task, 'ticker_arguments', 81)
        if block[:8] != b'UARG\0\1'+bytes((len(argv), 0)): raise AssertionError('argc')
        for i, value in enumerate(argv):
            address = int.from_bytes(block[8+2*i:10+2*i], 'little')
            if not 0x9a <= address <= 0xd0 or block[address-0x80:].split(b'\0', 1)[0] != value.encode():
                raise AssertionError(('argv', i, block.hex()))
        if block[8+2*len(argv):26] != bytes(18-2*len(argv)): raise AssertionError('argv NULL')
        _, base, limit, stack, _, _ = next(row for row in ALLOCATIONS if row[0] == task)
        installed = relocate_executable(apps['TICKER'], base, limit-base)[16:]
        if capture(tag+'-code', base, len(installed), 'worker') != installed: raise AssertionError('code damage')
        for offset in (0, 0xb0):
            if capture(tag+'-guard-'+str(offset), stack+offset, 16, 'worker') != b'\xa5'*16:
                raise AssertionError('stack guard')
        records.append(dict(check=tag, task=task, argv=argv, console=screen(tag+'-console'),
                            private_state=True, code_and_guards=True))
        print('PASS', tag, 'task', task, flush=True)

    def status(value):
        command('echo $?')
        # Peer writes may legally appear between the command echo and its
        # result; only each counted WRITE, not a whole command, is atomic.
        shown=screen()
        result=shown.rsplit('UDEKS:~> echo $?\n',1)[-1].splitlines()
        if str(value) not in result or not shown.endswith('UDEKS:~>'):
            raise AssertionError(('shell status', value, screen()))

    try:
        sp.wait_for_byte(port, 0xf3e0, 2, time.monotonic()+240); prompt()
        sp.monitor_command(port, 'warp off')
        argv = ['ticker', 'a', 'B', 'c', 'D', 'e', 'F', 'last']
        command(' '.join(argv)+' &'); started(6)
        events(b'echo drft')
        events(scan=85); events(scan=85)  # keep cursor in the middle across output
        wait(lambda: byte(0xf159) == 7, 'edit cursor')
        before = screen('draft-before')
        finished(6, argv, 'shell-edit')
        after = screen('draft-after')
        if not before.endswith('UDEKS:~> echo drft') or not after.endswith('UDEKS:~> echo drft'):
            raise AssertionError(('draft damaged', before, after))
        if byte(0xf159) != 7: raise AssertionError('edit cursor moved')
        if 'tick 5\nticker: complete' not in after: raise AssertionError('WRITE chunks split or reordered')
        events(b'a\n'); prompt()
        wait(lambda: screen().endswith('echo draft\ndraft\nUDEKS:~>'), 'edited submission')
        status(0)  # background return 37 must not replace the shell status
        events(scan=83)  # last shell command is echo $?, history must still work
        wait(lambda: screen().endswith('UDEKS:~> echo $?'), 'history recall after output')
        events(b'\n'); prompt()

        command('xclock &'); wait(lambda: byte(0xf246) == 1, 'clock window')
        if 'BGREAD' in apps:
            command('bgread &'); wait(lambda: private('BGREAD', 6, 'input_checks')[0] > 0, 'background read denial')
        background, reader = (5, 3) if 'BGREAD' in apps else (6, 5)
        command('ticker Mixed-case while-reading &'); started(background)
        command('ask', True); wait(lambda: blocked(reader), 'foreground reader')
        events(b'input kept')
        finished(background, ['ticker', 'Mixed-case', 'while-reading'], 'application-edit')
        if not screen().endswith('input kept'): raise AssertionError('foreground input overwritten')
        before = byte(0xf3d8)
        events(b'\n'); prompt()
        wait(lambda: screen().endswith('input kept\ninput kept\nUDEKS:~>'), 'reader echo')
        if byte(0xf3d8) != before or private('ASK', reader, 'ask_error') != b'\0':
            raise AssertionError('foreground input stolen or executed')
        if 'BGREAD' in apps and private('BGREAD', 6, 'input_failure') != b'\0':
            raise AssertionError('background read allowed')
        if byte(0xf246) != 1: raise AssertionError('clock window lost')
        status(0)
        command('ticker again &'); started(background)
        command('ask', True); wait(lambda: blocked(reader), 'cancel reader')
        events(b'discard'); events(b'\3'); prompt(); status(130)
        finished(background, ['ticker', 'again'], 'background-after-cancel')
        status(0)  # preceding echo reset the status; peer exit must not change it
        for bad in ('&', 'ticker a b c d e f g h &'):
            command(bad); status(2)
        command('notfound arg &'); status(11)  # existing compatibility-loader NOT_FOUND
        command('xclock -q'); wait(lambda: byte(0xf246) == 0, 'clock close')
        if byte(0xf11b): raise AssertionError('canary failure')
        if (ROOT/f'build/boot/udeks.{args.format}').read_bytes() != source: raise AssertionError('source changed')
        (work/'report.json').write_text(json.dumps(dict(
            scope='background argv/prompt-safe output; keyboard injection; no native mouse or hardware claim',
            format=args.format, source_disk_sha256=hashlib.sha256(source).hexdigest(),
            fixture_sha256=hashlib.sha256(fixture).hexdigest(),
            apps={n: hashlib.sha256(d).hexdigest() for n, d in apps.items()},
            checks=records, foreground_input=True, background_read_errno=5 if 'BGREAD' in apps else None,
            history=True, cancellation=True, exit_status=True), indent=2)+'\n')
        print('PASS native console background jobs:', work, flush=True)
    finally:
        sp.terminate(proc, port); os.close(master)


if __name__ == '__main__': main()

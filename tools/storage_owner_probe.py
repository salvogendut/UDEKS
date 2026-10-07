#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cold boot, then retire leaked descriptors via REAL program lifecycle paths.

Only disposable disk copies are used. Input is injected at the keyboard queue;
test-client release flags are the only runtime patches. No syscall, dispatcher,
owner or cleanup implementation is replaced. This probe uses read streams;
public write/readback qualification lives in storage_public_probe.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from add_disk_apps import add_apps
from build_bootfs import build_bootfs
import build_d81 as d81
from build_d71 import sector_offset
from disk_shell_fixture import build_fixture
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_app_layout import ALLOCATIONS
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, monitor_command

ROOT = Path(__file__).resolve().parents[1]


def with_spawn_child(image, child):
    """Add the fixture to bootfs: legacy native SPAWN does not load disk files.

    Rewrite only the existing fixed-size bootfs envelope on a disposable copy.
    Preserve recovery entries, all other SCHEDOVR bytes and the DOS allocation.
    """
    offset, track, sector = (d81.sector_offset, 40, 3) if len(image) == d81.SIZE else (sector_offset, 18, 1)
    matches = [e for e in d81.entries(image, offset, track, sector)
               if e[0] == 0x82 and e[3:19].rstrip(b'\xa0') == b'SCHEDOVR']
    if len(matches) != 1: raise ValueError('expected one SCHEDOVR PRG')
    original = d81.file_bytes(image, matches[0], offset)
    if original[:2] != b'\0\x12': raise ValueError('secondary load address changed')
    start = 2+0xa000-0x1200
    fs = original[start:start+0x1000]
    if fs[:6] != b'UBFS\0\1' or fs[7] != 24: raise ValueError('invalid recovery bootfs')
    entries = []
    for i in range(fs[6]):
        entry = fs[16+24*i:40+24*i]
        address = int.from_bytes(entry[2:4], 'little')
        size = int.from_bytes(entry[4:6], 'little')
        entries.append((entry[8:8+entry[1]].decode('ascii'), fs[address:address+size]))
    replacement = build_bootfs(entries+[('child', child)]).ljust(0x1000, b'\0')
    changed = bytearray(original); changed[start:start+0x1000] = replacement
    result = bytearray(image); track, sector = matches[0][1:3]; cursor = 0
    while track:
        pos = offset(track, sector); track, sector = image[pos:pos+2]
        count = 254 if track else sector-1
        result[pos+2:pos+2+count] = changed[cursor:cursor+count]; cursor += count
    if cursor != len(original): raise ValueError('secondary chain length changed')
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive', choices=('1541', '1571', '1581'), default='1541')
    parser.add_argument('--output', type=Path, default=ROOT/'build/storage-owner/vice-1541')
    parser.add_argument('--recovery', action='store_true', help='qualify bootfs fallback and disk I/O instead of owner clients')
    args = parser.parse_args()
    work = args.output.resolve(); work.mkdir(parents=True, exist_ok=True)
    fixture = ROOT/'build/storage-owner'
    paths = [fixture/'foreground/LEAK.BIN', fixture/'holder/HOLD.BIN',
             fixture/'parent/PARENT.BIN']
    image = with_spawn_child(args.disk.read_bytes(), (fixture/'CHILD.BIN').read_bytes())
    image = add_apps(image, [(p.name, p.read_bytes()) for p in paths])
    if args.recovery: image = build_fixture(image, 'missing')
    disk = work/('ownership'+args.disk.suffix); disk.write_bytes(image)
    text = (ROOT/'build/8502/udeks-8502.map').read_text()
    segments = map_segments(text)
    queue = keyboard_queue_address(text, (ROOT/'build/8502/keyboard.s').read_text())
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    exports = map_exports((ROOT/'build/storage/module.map').read_text())
    generations = exports['_udeks_storage_generations'][0]
    cleanup = exports['_udeks_storage_cleanup_error'][0]
    base = dict((row[0], row[1]) for row in ALLOCATIONS)[6]
    maps = {name: map_exports((fixture/name/(name+'.map')).read_text()) for name in ('holder', 'parent')}
    port = choose_port(); records = []
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
        ('-console', '-jamaction', '5', '-drive8truedrive', '-drive8type', args.drive),
        log_path=work/'vice.log')

    def capture(tag, address, size, bank='kernel'):
        return sp.capture_blocks(port, [(work/(tag+'.bin'), address, address+size-1, bank)])[0]

    def wait(tag, address, expected, bank='kernel', seconds=120):
        deadline = time.monotonic()+seconds
        while True:
            actual = capture(tag, address, len(expected), bank)
            if actual == expected: return
            if tag in ('holder-stage', 'parent-ready', 'parent-completed') and actual[0] >= 0x80:
                raise AssertionError((tag, 'client rejected operation', actual.hex()))
            if time.monotonic() > deadline: raise AssertionError((tag, actual.hex(), expected.hex()))
            time.sleep(.05)

    def console():
        cells = capture('console', segments['LOWBSS'][0], 0x558)
        return '\n'.join(cells[i:i+64].decode('ascii', errors='replace').rstrip()
                         for i in range(0, 1365, 65))

    def command(line, contains='', status=None):
        wait('prompt', slots+1, b'\x04\x02')
        before = byte(port, 0xf3d8)
        type_command(port, queue, line, time.monotonic()+120)
        sp.wait_for_byte(port, 0xf3d8, (before+1)&255, time.monotonic()+120)
        wait('prompt', slots+1, b'\x04\x02')
        output = console()
        if contains not in output: raise AssertionError((line, output))
        if status is not None and byte(port, 0xf287) != status:
            raise AssertionError((line, 'exit', byte(port, 0xf287), output))
        records.append(dict(command=line, console=output, status=status))
        print('PASS', line, flush=True)

    def gen(tag):
        return capture('generation', generations+tag, 1, 'worker')[0]

    def retired(tag, before):
        wait('generation-'+str(tag), generations+tag, bytes(((before+1)&255,)), 'worker')
        wait('cleanup-errno', cleanup, b'\0', 'worker')
        records.append(dict(retired=tag, generation_before=before, generation_after=gen(tag)))

    def app(name, symbol): return maps[name][symbol][0]-0x1000+base

    def report():
        (work/'result.json').write_text(json.dumps(dict(
            drive=args.drive, recovery=args.recovery,
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),
            fixture_sha256=hashlib.sha256(image).hexdigest(), checks=records), indent=2)+'\n')

    try:
        if args.recovery:
            sp.wait_for_byte(port, 0xf3d9, 0xa5, time.monotonic()+240)
            sp.wait_for_byte(port, 0xf3dd, 2, time.monotonic()+10)
            command('echo recovery-ok', 'recovery-ok')
            command('mount 8 /mnt', 'mount: /mnt ready')
            command('/mnt/COWSAY.BIN recovery-alive', 'recovery-alive', 0)
            command('umount /mnt')
            command('echo recovery-cleanup-ok', 'recovery-cleanup-ok')
            report()
            return
        sp.wait_for_byte(port, 0xf3e0, 2, time.monotonic()+240)
        command('cat /hello', 'HELLO UDEKS', 0)
        # Two different synchronous invocations must not share an open stream.
        for _ in range(2):
            before = gen(9)
            command('leak', status=0)
            retired(9, before)
            command('cat /hello', 'HELLO UDEKS', 0)
        # A native client holds a descriptor across cooperative YIELD calls.
        # Return goes through the scheduler EXIT handler, not a monitor hook.
        for _ in range(2):
            before = gen(6)
            command('hold &')
            wait('holder-stage', app('holder', '_owner_stage'), b'\2', 'worker')
            sp.write_blocks(port, [(app('holder', '_owner_release'), b'\1')], 'worker')
            wait('holder-completed', app('holder', '_owner_stage'), b'\3', 'worker')
            wait('holder-free', slots+5*8+1, b'\0')
            retired(6, before)
            command('cat /hello', 'HELLO UDEKS', 0)
        # Parent SPAWNs a child; child OPENs and yields; parent CANCELs then
        # WAITPIDs it, opens the file again itself, and EXITs without CLOSE.
        parent_before, child_before = gen(6), gen(2)
        command('parent &')
        wait('parent-ready', app('parent', '_parent_stage'), b'\2', 'worker')
        wait('child-holds-stream', 0x02f0, b'\2', 'worker')
        sp.write_blocks(port, [(app('parent', '_parent_release'), b'\1')], 'worker')
        wait('parent-completed', app('parent', '_parent_stage'), b'\4', 'worker')
        wait('parent-free', slots+5*8+1, b'\0')
        wait('child-reaped', slots+8+1, b'\0')
        retired(2, child_before); retired(6, parent_before)
        command('cat /hello', 'HELLO UDEKS', 0)
        # Real native graphics plus disk I/O after the cleanup paths.
        command('xclock &')
        sp.wait_for_byte(port, 0xf246, 1, time.monotonic()+120)
        command('cat /hello', 'HELLO UDEKS', 0)
        command('xclock -q')
        sp.wait_for_byte(port, 0xf246, 0, time.monotonic()+120)
        command('echo ownership-ok', 'ownership-ok')
        if byte(port, 0xf11b): raise AssertionError('task canary failure')
        report()
    except Exception:
        print('parent status:', capture('parent-error', app('parent', '_parent_error'), 2, 'worker').hex(), flush=True)
        print('ownership state:', capture('failure-generations', generations, 12, 'worker').hex(), flush=True)
        print(console(), flush=True)
        print(monitor_command(port, 'r').decode(errors='replace'), flush=True)
        capture('failure-tasks', slots, 64)
        capture('failure-request', 0xf359, 38)
        capture('failure-storage', 0xe000, 384, 'worker')
        raise
    finally:
        sp.terminate(proc, port)
        os.close(master)


if __name__ == '__main__': main()

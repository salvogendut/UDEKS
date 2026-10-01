#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise banked delivery, optionally native C tasks, from the service poll.

No CPU takeover or synthetic task execution: the normal kernel poll invokes
the private gate, restores the hook and continues. Fixtures have no graphics
bindings; --native qualifies task execution, not banked graphics rendering.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from build_d71 import install_prg_file
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command, console_address
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, monitor_command

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = 0x0C00
REQUEST = 0xF359


def fixture(base, size=257, bss=31):
    """Managed table plus inert RTS callbacks and a nonzero copy-test pattern."""
    if size < 19 or size > 0xFFFF:
        raise ValueError('invalid fixture size')
    header = b'UDEX\0\1\1\2' + b''.join(n.to_bytes(2, 'little')
        for n in (base, size, bss, base))
    image = (b'\x4c' + (base+18).to_bytes(2, 'little')) * 6 + b'\x60'
    image += bytes((i % 255)+1 for i in range(size-len(image)))
    return header+image


def request_record(name):
    text = name.encode('ascii')
    if len(text) > 16:
        raise ValueError('basename too long')
    record = bytearray(b'UTRQ\0\10' + bytes((1, 0x71, 0xA9, 0, 17, 0, 0, 0)) + bytes(24))
    record[14] = len(text)
    record[15:31] = text.ljust(16, b'\0')
    return bytes(record)


def poll_hook(poll, original, selector, record, gate=0xF91C):
    """Use the graphics-module reservation BEFORE its lazy installation only."""
    code = bytearray(b'\x08\x48\x8a\x48\x98\x48')  # P,A,X,Y
    def absolute(opcode, address):
        code.extend(bytes((opcode,)) + address.to_bytes(2, 'little'))
    code.extend(b'\xa2\x25')
    absolute(0xBD, REQUEST)
    absolute(0x9D, SCRATCH+0x100)
    code.extend(b'\xca\x10\xf7')
    # Constants at +$A0; response +$C6; errno +$EC; done +$ED.
    code.extend(b'\xa2\x25')
    absolute(0xBD, SCRATCH+0xA0)
    absolute(0x9D, REQUEST)
    code.extend(b'\xca\x10\xf7')
    code.extend(bytes((0xA9, selector)))
    absolute(0x20, gate)
    absolute(0x8D, SCRATCH+0xEC)
    code.extend(b'\xa2\x25')
    absolute(0xBD, REQUEST)
    absolute(0x9D, SCRATCH+0xC6)
    code.extend(b'\xca\x10\xf7')
    # Observe restored kernel mapping before returning to resident code.
    absolute(0xAD, 0xFF00)
    absolute(0x8D, SCRATCH+0xEE)
    code.extend(b'\xa2\x25')
    absolute(0xBD, SCRATCH+0x100)
    absolute(0x9D, REQUEST)
    code.extend(b'\xca\x10\xf7')
    for index, value in enumerate(original):
        code.extend(bytes((0xA9, value)))
        absolute(0x8D, poll+index)
    code.extend(b'\xa9\x01')
    absolute(0x8D, SCRATCH+0xED)
    code.extend(b'\x68\xa8\x68\xaa\x68\x28')
    absolute(0x4C, poll)
    if len(code) > 0xA0 or len(record) != 38 or len(original) != 3:
        raise ValueError('probe hook exceeds scratch')
    return (code.ljust(0xA0, b'\0')+record+bytes(41)).ljust(0x140, b'\0')+b'\xa9\x16\x60'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive', choices=('1541','1571'), default='1541')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native', action='store_true', help='also execute compiled banked C clients')
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    kernel_map = (ROOT/'build/8502/udeks-8502.map').read_text()
    segments = map_segments(kernel_map)
    if segments['GRAPHICSCODE'][0] != SCRATCH or segments['GRAPHICSCODE'][1]>=0x1200:
        raise ValueError('probe scratch reservation changed')
    exports=map_exports(kernel_map)
    poll = exports['_udeks_managed_apps_poll'][0]
    installed = exports['_udeks_banked_graphics_installed'][0]
    symbols = map_exports((ROOT/'build/boot/banked-loader.map').read_text())
    owned = symbols['banked_owned'][0]
    headers = symbols['banked_headers'][0]
    slots = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    queue = keyboard_queue_address(kernel_map, (ROOT/'build/8502/keyboard.s').read_text())
    files = {'load3': fixture(0x2300), 'load4': fixture(0x3500),
             'full3': fixture(0x2300, 0x1200-16, 16),
             'full4': fixture(0x3500, 0xB00-16, 16),
             'over': fixture(0x2300, 0x1200-15, 0),
             'short': b'UDEX', 'trail': fixture(0x2300)+b'\0'}
    mutations = {'magic': (0, 0), 'minor': (5, 2), 'cpu': (6, 2),
                 'flags': (7, 4), 'load': (9, 0x35), 'entry': (14, 1),
                 'size': (10, 0), 'bss': (13, 0xFF), 'opcode': (16, 0x60),
                 'vector': (17, 3), 'outside': (18, 0x35)}
    for name, (offset, value) in mutations.items():
        data = bytearray(files['load3'])
        data[offset] = value
        files[name] = bytes(data)
    native_maps = {}
    context_base = map_exports((ROOT/'build/8502/task-context-binding.map').read_text())['_udeks_task_contexts_private'][0]
    scheduler_exports = scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')
    wait_base = scheduler_exports['_udeks_task_wait_state_private']
    if args.native:
        for tag in (3,4):
            name = 'native'+str(tag)
            files[name] = (ROOT/('build/four-apps/native/'+name+'.udx')).read_bytes()
            native_maps[tag] = map_exports((ROOT/('build/four-apps/native/'+name+'.map')).read_text())
    disk_image = bytearray(args.disk.read_bytes())
    for name, data in files.items():
        install_prg_file(disk_image, name.upper()+'.BIN', data, file_type=0x81)
    disk = work/('test'+args.disk.suffix)
    disk.write_bytes(disk_image)
    port = choose_port()
    proc, master = sp.launch_vice(disk, port, 'net.sf.VICE',
        ('-console', '-drive8truedrive', '-drive8type', args.drive, '-jamaction', '5',
         '-logfile', str(work/'vice.log')), log_path=work/'vice-console.log')
    records = []

    def capture(name, address, size, bank='kernel'):
        return sp.capture_blocks(port, [(work/(name+'.bin'), address, address+size-1, bank)])[0]

    def invoke(selector, name, error=0, record=None, gate=0xF91C):
        if capture('graphics-installed',installed,1)!=b'\0':
            raise ValueError('graphics module owns the probe scratch; refusing overwrite')
        request = request_record(name) if record is None else record
        original = capture('poll', poll, 3)
        stub = poll_hook(poll, original, selector, request, gate)
        sp.write_kernel_blocks(port, [(SCRATCH, stub),
            (poll, b'\x4c'+SCRATCH.to_bytes(2, 'little'))])
        deadline = time.monotonic()+120
        while capture('response', SCRATCH+0xC6, 41)[39] != 1:
            if time.monotonic() > deadline:
                raise TimeoutError('banked service did not return: '+name)
            time.sleep(.05)
        response = capture('response', SCRATCH+0xC6, 41)
        if response[:38] != request or response[38] != error or response[40] != 0x3E:
            raise AssertionError((selector, name, error, response.hex(), request.hex()))
        if capture('poll-after', poll, 3) != original:
            raise AssertionError('poll hook not restored')
        records.append(dict(selector=selector, name=name, errno=error,
                            request_preserved=True, kernel_map_restored=True))
        print('PASS', hex(selector), name, error, flush=True)

    def command(text, expected):
        deadline = time.monotonic()+120
        sp.wait_for_byte(port, slots+1, 4, deadline)
        before = byte(port, 0xF3D8)
        type_command(port, queue, text, deadline)
        sp.wait_for_byte(port, 0xF3D8, (before+1)&255, deadline)
        while time.monotonic() < deadline:
            cells = capture('console', console_address(), 0x558)
            console = '\n'.join(cells[i:i+64].decode('ascii', errors='replace')
                                for i in range(0, 21*65, 65))
            if expected in console:
                break
            time.sleep(.1)
        else:
            raise AssertionError(text+'\n'+console)
        print('PASS console', text, flush=True)

    def allocation(slot):
        base, size = (0x2300, 0x1200) if slot == 3 else (0x3500, 0xB00)
        return capture('app'+str(slot), base, size, 'worker')

    def verify_loaded(slot, name):
        data = files[name]
        size, bss = (int.from_bytes(data[n:n+2], 'little') for n in (10, 12))
        if allocation(slot)[:size+bss] != data[16:]+bytes(bss):
            raise AssertionError('image/BSS differs: '+name)
        if capture('headers', headers+16*(slot-3), 16, 'worker') != data[:16]:
            raise AssertionError('validated header not retained')

    def native_byte(tag, name, size=1):
        address = native_maps[tag]['_probe_'+name][0]
        return int.from_bytes(capture('native'+str(tag)+'-'+name, address, size, 'worker'), 'little')

    def wait_native(tag, exited=False):
        deadline = time.monotonic()+90
        while time.monotonic() < deadline:
            state = capture('native-state', slots+(tag-1)*8,8)
            if native_byte(tag,'error'):
                raise AssertionError(('native C self-check',tag,native_byte(tag,'error')))
            if exited:
                if state[1] == 6:
                    if state[4] != 40+tag: raise AssertionError(('native exit',tag,state.hex()))
                    return
            elif native_byte(tag,'ready') == 0xA5 and native_byte(tag,'progress',2) >= 8:
                return
            time.sleep(.05)
        raise TimeoutError(('native client',tag,exited))

    def finish_native(tag):
        sp.write_blocks(port, [(native_maps[tag]['_probe_control'][0], b'\1')], 'worker')
        wait_native(tag, True)
        progress = native_byte(tag,'progress',2)
        value = native_byte(tag,'value',2)
        low_sp = native_byte(tag,'low_sp',2)
        bottom, top, page = (0x8A00,0x8CB0,0xD600) if tag==3 else (0x8D00,0x8FB0,0xD800)
        if value != (tag*1000+tag*progress)&65535:
            raise AssertionError(('private state crossed',tag,progress,value))
        if not bottom+16 <= low_sp < top-64:
            raise AssertionError(('C stack was not exercised safely',tag,hex(low_sp)))
        for name, address, size in (('bottom',bottom,16),('top',top,16),('cpu-stack',page,1)):
            if capture('native'+str(tag)+'-'+name,address,size,'worker') != b'\xa5'*size:
                raise AssertionError(('guard overwritten',tag,name))
        records.append(dict(native_task=tag, progress=progress,value=value,
                            lowest_software_sp=low_sp,exit_status=40+tag,guards_ok=True))
        print('PASS native C',tag,'steps',progress,'stack low',hex(low_sp),'exit',40+tag,flush=True)

    try:
        sp.wait_for_byte(port, 0xF3E0, 2, time.monotonic()+240)
        invoke(2, 'harness', 22, gate=SCRATCH+0x140)
        invoke(2, 'invalid', 22)
        command('xclock &', 'xclock started &')
        command('xwave &', 'xwave started &')
        sp.wait_for_byte(port, 0xF27A, 21, time.monotonic()+90)
        protected = [('clock-code',0x200,len((ROOT/'build/user/xclock.udx').read_bytes())-16,'kernel'),
                     ('wave-code',0x1200,len((ROOT/'build/user/xwave.udx').read_bytes())-16,'kernel'),
                     ('z80-code',0x2000,663,'worker')]
        before = [capture(n,a,s,b) for n,a,s,b in protected]
        invoke(3, 'load3')
        verify_loaded(3, 'load3')
        invoke(4, 'load4')
        verify_loaded(4, 'load4')
        invoke(0x43, '', 8)          # a managed callback image must not execute
        peer = allocation(4)
        own = allocation(3)
        invoke(3, 'full3', 16)
        if allocation(3) != own: raise AssertionError('owned slot overwritten')
        for slot in (2, 3, 4):
            for state in (5, 6):  # fault-injected ownership, not scheduled tasks
                address = slots + (slot-1)*8+1
                target = 3 if slot == 2 else slot
                sp.write_kernel_blocks(port, [(address, bytes((state,)))])
                invoke(0x80 | target, '', 16)
                invoke(target, 'load'+str(target), 16)
                sp.write_kernel_blocks(port, [(address, b'\0')])
        invoke(0x83, '')
        if capture('released', owned, 2, 'worker') != b'\0\1':
            raise AssertionError('release disturbed peer ownership')
        if capture('cleared-header', headers, 16, 'worker') != bytes(16):
            raise AssertionError('release retained header')
        for name in ('short', 'trail', *mutations):
            invoke(3, name, 12 if name == 'bss' else 8)
            if capture('rejected-owned', owned, 2, 'worker') != b'\0\1':
                raise AssertionError('invalid image published ownership')
        invoke(3, 'over', 12)
        invoke(3, 'absent', 2)
        invoke(2, 'load3', 22)
        invoke(5, 'load3', 22)
        invoke(3, '../bad', 22)
        bad = bytearray(request_record('load3')); bad[30] = 1
        invoke(3, 'padding', 22, bytes(bad))
        if allocation(4) != peer: raise AssertionError('peer image changed on rejection')
        invoke(3, 'full3')
        verify_loaded(3, 'full3')
        invoke(0x84, '')
        invoke(4, 'full4')
        verify_loaded(4, 'full4')
        if args.native:
            invoke(0x83,'')
            invoke(0x84,'')
            for tag in (3,4):
                invoke(tag,'native'+str(tag))
                verify_loaded(tag,'native'+str(tag))
                invoke(0x40|tag,'')
            wait_native(3)
            wait_native(4)
            for tag in (3,4):
                invoke(0x40|tag,'',16)
                invoke(0x80|tag,'',16)
                invoke(0xC0|tag,'',16)
            command('cowsay four contexts', 'four contexts')
            for tag in (3,4):
                finish_native(tag)
                invoke(0x80|tag,'',16)  # zombies still own their allocation
            # A kernel-only reap must still reject an unrelated allocation.
            original = capture('zombie-before-parent-fault', slots+16,8)
            sp.write_kernel_blocks(port, [(slots+16, b'\2')])
            invoke(0xC3,'',22)
            if capture('zombie-after-parent-fault',slots+16,8) != b'\2'+original[1:]:
                raise AssertionError('rejected reap changed lifecycle metadata')
            sp.write_kernel_blocks(port, [(slots+16,original[:1])])
            sp.write_blocks(port, [(owned,b'\0')], 'worker')
            invoke(0xC3,'',22)
            sp.write_blocks(port, [(owned,b'\2')], 'worker')
            for tag in (3,4):
                invoke(0xC0|tag,'')
                if capture('reaped-task'+str(tag),slots+(tag-1)*8,8) != bytes(8):
                    raise AssertionError('native task metadata survived reap')
                if capture('reaped-context'+str(tag),context_base+(tag-1)*11,11) != bytes(11):
                    raise AssertionError('native context survived reap')
                waits = capture('reaped-waits',wait_base,80)
                if any(waits[index*8+tag-1] for index in range(10)):
                    raise AssertionError('native wait snapshot survived reap')
            # Reload resets DATA/BSS and must not inherit the old context or wait.
            invoke(3,'native3')
            verify_loaded(3,'native3')
            invoke(0x43,'')
            wait_native(3)
            finish_native(3)
            invoke(0xC3,'')
        after = [capture('after-'+n,a,s,b) for n,a,s,b in protected]
        if before != after: raise AssertionError('legacy apps or Z80 overwritten')
        command('cowsay banks alive', 'banks alive')
        command('xwave -q', 'xwave stopped')
        command('xclock -q', 'xclock stopped')
        command('xcalc &', 'xcalc started &')  # boot scratch at $0C00 now disposable
        command('echo calculator alive', 'calculator alive')
        if byte(port, 0xF11B): raise AssertionError('lifecycle canary failure')
        (work/'result.json').write_text(json.dumps(dict(
            disk_sha256=hashlib.sha256(disk_image).hexdigest(),
            loader_sha256=hashlib.sha256((ROOT/'build/boot/banked-loader.bin').read_bytes()).hexdigest(),
            drive=args.drive, load_only=not args.native, records=records,
            legacy_code_preserved=True, console_alive=True), indent=2)+'\n')
    except Exception:
        print(monitor_command(port,'r').decode(errors='replace'), flush=True)
        capture('failure-loader',0xD900,0x700,'worker')
        raise
    finally:
        sp.terminate(proc,port)
        os.close(master)


if __name__ == '__main__':
    main()

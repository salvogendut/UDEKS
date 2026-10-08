#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute production request gates/router/manager/SDK together under sim6502.

Only unrelated kernel entries (BRK traps), startup, and banked storage transport
are stubbed. The sealed C time module is unmodified. This is not disk/IRQ/CIA
hardware qualification; CIA and MMU addresses are simulator RAM.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from gen_capability_imports import map_exports
from build_scheduler_overlay import map_segments

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT/'build/services/request'
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').unlink(missing_ok=True)

    def run(*args):
        subprocess.run(args, cwd=ROOT, check=True)

    def assemble(name, source, *flags):
        obj = out/(name+'.o')
        run('ca65', '-I', 'src/8502', '-I', str(out), *flags, '-o', str(obj), str(source))
        return str(obj)

    sdk = assemble('sdk', 'user/lib/service_request.s')
    (out/'errno.s').write_text('.export _udeks_errno\n.segment "BSS"\n_udeks_errno: .res 1\n')
    errno = assemble('errno', out/'errno.s')
    (out/'sdk.cfg').write_text('MEMORY { Z: start=$02,size=$1e,file=""; R: start=$A000,size=$c00,file=%O; }\n'
        'SEGMENTS { ZEROPAGE: load=Z,type=zp; CODE: load=R,type=rw; RODATA: load=R,type=ro; BSS: load=R,type=bss; }\n')
    run('cl65', '-t', 'none', '-C', str(out/'sdk.cfg'), '-m', str(out/'sdk.map'),
        '-u', '_udeks_errno', '-u', '_udeks_service_control', '-o', str(out/'sdk.bin'), sdk, errno)
    sdk_symbols = map_exports((out/'sdk.map').read_text())
    if any(end >= 0xa780 for name,(_,end,_) in map_segments((out/'sdk.map').read_text()).items() if name!='ZEROPAGE'):
        raise ValueError('SDK overlaps the wrong-stack negative-control guard')
    gate = assemble('gate', 'src/8502/syscall_gate.s', '-D', 'UDEKS_DISK_TIME')
    # Only unrelated kernel imports are traps. All service-manager, envelope,
    # signature, reply and SDK instructions are the actual candidate sources.
    dump = subprocess.run(['od65', '--dump-imports', gate], check=True, text=True, capture_output=True).stdout
    imports = set(re.findall(r'Name:\s*"(_udeks_[^"]+)"', dump))
    provided = {'_udeks_time_slot_control', '_udeks_time_slot_state', '_udeks_time_slot_reset',
                '_udeks_time_slot_set', '_udeks_bootfs_finish_ok', '_udeks_bootfs_finish_error', '_udeks_bootfs_request'}
    (out/'traps.s').write_text('.import test_trap\n'+''.join(f'.export {name} = test_trap\n' for name in sorted(imports-provided))+
        f'.export test_sdk_entry = ${sdk_symbols["_udeks_service_control"][0]:04x}\n')
    # Router binds to the real request entry via the linker, not a duplicate.
    (out/'disk-loader-bindings.inc').write_text('STORAGE_CURRENT_TASK = $f110\n'
        '.import _udeks_bootfs_finish_error, _udeks_time_slot_request\n'
        'STORAGE_FINISH_ERROR = _udeks_bootfs_finish_error\nTIME_MODULE_REQUEST = _udeks_time_slot_request\n')
    router_source = (ROOT/'src/services/filesystem/iec_router.s').read_text()
    if router_source.count('.segment "CODE"') != 1:
        raise ValueError('router segment declaration changed')
    # Only rename the segment so it can share one ld65 fixture link; every
    # instruction and assertion still comes from the production source.
    (out/'router.s').write_text(router_source.replace('.segment "CODE"', '.segment "ROUTER"'))
    objects = [gate, assemble('traps', out/'traps.s'),
        assemble('core', 'src/services/module/time_slot.s'),
        assemble('start', 'src/8502/service_start.s'),
        assemble('runtime', 'src/services/time/runtime.s'),
        assemble('fixture', 'bench/time-module/request_fixture.s'),
        assemble('router', out/'router.s', '-D', 'UDEKS_DISK_TIME'),
        assemble('bootfs', 'src/services/filesystem/bootfs_request.s')]
    cfg = ('MEMORY { ROOT: start=$8000,size=$1000,file=%O;\n'+
        ''.join(f'{label}: start=${base:04x},size=${size:x},file="{out/name}.bin";\n' for label,base,size,name in
                [('R',0xc880,128,'router'),('G',0xcf00,256,'gate'),('Q',0xf800,272,'common'),('B',0xf3ef,667,'bootfs')])+
        '}\nSEGMENTS { HEADER: load=ROOT,type=ro; CODE: load=ROOT,type=rw; RODATA: load=ROOT,type=ro; '
        'DATA: load=ROOT,type=rw,optional=yes; BSS: load=ROOT,type=bss,define=yes; '
        'ROUTER: load=R,type=rw; SYSCALLS: load=G,type=rw; TASKREQUEST: load=Q,type=rw; BOOTFSCODE: load=B,type=rw; }\n')
    (out/'fixture.cfg').write_text(cfg)
    run('cl65', '-t', 'none', '-C', str(out/'fixture.cfg'), '-m', str(out/'fixture.map'),
        '-o', str(out/'request.bin'), *objects)
    parts = [('module', ROOT/'build/services/time/TIME.SVC')]+[(name,out/(name+'.bin')) for name in
        ('request','sdk','router','gate','common','bootfs')]
    embed = '.segment "RODATA"\n'
    for name, path in parts:
        embed += f'.export _{name}_image, _{name}_size\n_{name}_image: .incbin "{path}"\n_{name}_size: .word {path.stat().st_size}\n'
    embed += f'.export _sdk_errno\n_sdk_errno: .word {sdk_symbols["_udeks_errno"][0]}\n'
    (out/'embed.s').write_text(embed)
    harness = []
    for name, source in [('check','bench/time-module/request_check.c'), ('call','bench/time-module/call.s'),('embed',str(out/'embed.s'))]:
        obj = out/(name+'.o')
        run('cl65', '-t', 'sim6502', '-Oirs', '-c', '-o', str(obj), source)
        harness.append(str(obj))
    run('cl65', '-t', 'sim6502', '-m', str(out/'check.map'), '-o', str(out/'check.sim65'), *harness)
    if any(end >= 0x8000 for name,(_,end,_) in map_segments((out/'check.map').read_text()).items() if name!='ZEROPAGE'):
        raise ValueError('simulator harness overlaps the candidate fixture')
    result = subprocess.run(['sim65', str(out/'check.sim65')], cwd=ROOT, capture_output=True, text=True, timeout=60)
    (out/'check.log').write_text(result.stdout+result.stderr)
    print(result.stdout+result.stderr, end='')
    result.check_returncode()
    # Remove precisely the private->root software-stack binding. The test
    # must detect writes through the poisoned old sp=$A7A6 even though that
    # RAM is writable and the C function can otherwise appear to succeed.
    original_sdk = (out/'sdk.bin').read_bytes()
    bridge = bytes.fromhex('a5 02 85 06 a5 03 85 07')
    if original_sdk.count(bridge) != 1:
        raise ValueError('runtime-bridge negative-control instructions changed')
    (out/'sdk-negative.bin').write_bytes(original_sdk.replace(bridge, b'\xea'*8))
    (out/'negative-embed.s').write_text(embed.replace(str(out/'sdk.bin'), str(out/'sdk-negative.bin')))
    negative = assemble('negative-embed', out/'negative-embed.s')
    run('cl65', '-t', 'sim6502', '-o', str(out/'negative.sim65'), *harness[:2], negative)
    failed = subprocess.run(['sim65', str(out/'negative.sim65')], cwd=ROOT, capture_output=True, text=True, timeout=60)
    (out/'negative.log').write_text(failed.stdout+failed.stderr)
    if not failed.returncode or 'FAIL request' not in failed.stdout:
        raise AssertionError('negative control failed to detect the missing runtime-stack bridge')
    print('PASS negative control: missing private/root software-stack bridge detected')
    report = {'scope':'CPU request/router/SDK integration; RAM-backed CIA, no disk/boot qualification',
              'negative_control':'missing private/root software-stack bridge detected',
              'images':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in parts}}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()

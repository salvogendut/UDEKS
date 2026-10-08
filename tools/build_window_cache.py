#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate private cache bindings from the currently linked service module."""
import argparse
import json
import re
from pathlib import Path

from build_scheduler_overlay import map_segments
from service_image import TIME_BASE, TIME_LIMIT

CORE = 0x4200
HEADER = 0x5210
SCHEDULER_SOURCE = 0x6000
CAPACITY = 2224
FROZEN_RANGES = {
    'ZEROPAGE': (0x0004, 0x001f), 'PROBECODE': (0x0b00, 0x0bd0),
    'LOWBSS': (0x9b00, 0xa0fc), 'STARTUP': (0x1c00, 0x1cce),
    'KERNELENTRY': (0x2000, 0x2005), 'CODE': (0x2006, 0x9330),
    'RODATA': (0x9331, 0x9f24), 'DATA': (0x9f25, 0x9f27),
    'BSS': (0x9f28, 0xa1df), 'VICSHADOW': (0xa1e0, 0xc11f),
    'SYSCALLS': (0xcf00, 0xcffe), 'HIGHBSS': (0xe1b8, 0xe2e1),
    'MODULECODE': (0xe300, 0xe5fa), 'MODULERODATA': (0xe5fb, 0xe643),
    'BOOTFSCODE': (0xf3ef, 0xf688), 'TASKREQUEST': (0xf800, 0xf904),
    'TASKGATE': (0xff05, 0xffc4),
}


def glyph_overlay_layout(segments):
    """A post-upload overlay may replace glyph bytes, never header or maps."""
    if segments.get('VDCASSETS') != (0x96a8, 0x9aff, 1112):
        raise ValueError('VDC boot asset reservation changed')
    state, last, count = segments.get('PATHSTATE', (0, 0, 0))
    start, end, size = segments.get('GRAPHICSPATHS', (0, 0, 0))
    if (state!=0x96b8 or not 0<count==last-state+1 or start!=last+1 or
            not 0<size==end-start+1 or end>=0x9aa8):
        raise ValueError('graphics paths overlay exceeds retired glyph bytes')
    if segments['BSS'][1] >= 0x96a8:
        raise ValueError('resident reaches boot assets')


def layout_maps(normal, panic):
    expected = {name: (start, end, end - start + 1)
                for name, (start, end) in FROZEN_RANGES.items()}
    # Command extraction may shrink ordinary resident code/data, HIGHBSS and
    # the request implementation. Cache/staging/public gate addresses may not
    # move. Require normal/panic parity and prove each flexible reservation.
    flexible = {'CODE', 'RODATA', 'DATA', 'BSS', 'HIGHBSS', 'TASKREQUEST', 'MODULECODE', 'MODULERODATA'}
    actual = map_segments(normal)
    extra = {'GRAPHICSCODE', 'GRAPHICSHELP'} & actual.keys()
    if extra and extra != {'GRAPHICSCODE', 'GRAPHICSHELP'}:
        raise ValueError('incomplete banked graphics module layout')
    for name, start, limit in (('GRAPHICSCODE',0x0c00,0x1300),('GRAPHICSHELP',0xa100,0xa1e0)):
        if name in extra:
            low,end,size = actual[name]
            if low != start or not 0 < size == end-low+1 <= limit-low:
                raise ValueError('banked graphics exceeds reservation: '+name)
    overlay = {'VDCASSETS', 'PATHSTATE', 'GRAPHICSPATHS'} & actual.keys()
    if overlay:
        if overlay != {'VDCASSETS', 'PATHSTATE', 'GRAPHICSPATHS'} or len(extra) != 2:
            raise ValueError('incomplete glyph overlay layout')
        glyph_overlay_layout(actual)
        extra |= overlay
    if 'SERVICEBOOT' in actual:
        # Time-service startup may occupy ONLY its explicitly retired slot.
        # This is not permission to move a cache, VDC, app or stack boundary.
        low, end, size = actual['SERVICEBOOT']
        if (len(overlay) != 3 or low != TIME_BASE or not 0 < size == end-low+1 or
                end >= TIME_LIMIT or actual['BSS'][1] >= TIME_BASE):
            raise ValueError('service startup overlay exceeds its reservation')
        extra.add('SERVICEBOOT')
    for label, text in (('normal', normal), ('panic', panic)):
        current = map_segments(text)
        if current.keys() != expected.keys() | extra or current != actual or any(
                current[name] != bounds for name, bounds in expected.items()
                if name not in flexible):
            raise ValueError('frozen cache integration layout changed: ' + label)
        cursor = 0x2006
        for name in ('CODE', 'RODATA', 'DATA', 'BSS'):
            start, end, size = current[name]
            if start != cursor or size <= 0 or end != start + size - 1 or end >= 0x9b00:
                raise ValueError('resident command region exceeds reservation: ' + name)
            cursor = end + 1
        for name, start, limit in (('HIGHBSS', 0xe1b8, 0xe2e2), ('TASKREQUEST', 0xf800, 0xf909)):
            low, end, size = current[name]
            if low != start or size <= 0 or end != low + size - 1 or end >= limit:
                raise ValueError('resident reservation changed: ' + name)
        start, end, size = current['MODULECODE']
        rstart, rend, rsize = current['MODULERODATA']
        if start != 0xe300 or end+1 != rstart or rend >= 0xe644 or size != end-start+1 or rsize != rend-rstart+1:
            raise ValueError('high module exceeds reservation')
    return actual


def identity(module):
    if not module or len(module) > HEADER - CORE:
        raise ValueError('cache module reaches identity or is empty')
    return (b'VCC2\x00\x01' + CORE.to_bytes(2, 'little') +
            len(module).to_bytes(2, 'little') +
            (sum(module) & 65535).to_bytes(2, 'little') +
            (0x42d5).to_bytes(2, 'little') + CAPACITY.to_bytes(2, 'little'))


def bindings(module, gateway, map_text):
    segments = map_segments(map_text)
    if segments['OVERLAY'] != (CORE, 0x42d4, 213) or segments['DISPATCH'][0] != 0x42d5:
        raise ValueError('row core or dispatcher placement changed')
    source, end, size = segments['GATEIMAGE']
    if size != len(gateway) or end + 1 != CORE + len(module) or module[source-CORE:] != gateway:
        raise ValueError('gateway image is not the exact module suffix')
    # The fully charged resident diagnostic reset uses these two operands.
    if len(gateway) != 196 or gateway.count(bytes.fromhex('689506e8')) != 1 or \
            gateway.index(bytes.fromhex('689506e8')) + 2 + 0xf68a != 0xf6c1 or \
            gateway.count(bytes.fromhex('a9538507')) != 1 or \
            gateway.index(bytes.fromhex('a9538507')) + 1 + 0xf68a != 0xf6a4:
        raise ValueError('qualified gateway operand layout changed')
    if segments.get('DATA', (0, 0, 0))[2] != 3 or \
            segments['PRIVATESTATE'] != (0x5220, 0x5239, 26):
        raise ValueError('cache private state placement changed')
    header = identity(module)
    last_page, last_bytes = divmod(len(module) - 1, 256)
    acceptance = (f'CACHE_LAST_PAGE = ${last_page:02x}\n'
                  f'CACHE_LAST_BYTES = ${(last_bytes + 1) & 255:02x}\n'
                  f'CACHE_CHECKSUM = ${sum(module) & 65535:04x}\n'
                  '.macro CACHE_EXPECTED_HEADER\n.byte ' +
                  ','.join(f'${b:02x}' for b in header) + '\n.endmacro\n')
    loader = f'GATE_SOURCE = ${source:04x}\nGATE_BYTES = ${len(gateway):02x}\n'
    return acceptance, loader


def write_changed(path, value):
    """Keep configuration timestamps stable for no-op make invocations."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != value:
        path.write_bytes(value)


def wrap_scheduler(payload, constants, module):
    """Relocate only temporary sources; installed scheduler addresses stay put."""
    if payload[:8] != b'\x00\x50USOV\x00\x03':
        raise ValueError('cache requires canonical $5000 USOV 0.3 input')
    if SCHEDULER_SOURCE + len(payload) - 2 > 0x7fc0:
        raise ValueError('secondary sources reach sprite memory')
    moved = ('SCHEDULER_OVERLAY_LOAD', 'SCHEDULER_OVERLAY_END',
             'SCHEDULER_OVERLAY_PAGE_SOURCE', 'SCHEDULER_OVERLAY_TAIL_SOURCE',
             'TASK_ACTIVATION_CONTEXT_SOURCE', 'TASK_ACTIVATION_TAIL_SOURCE')
    for name in moved:
        matches = re.findall(r'^' + name + r' = \$([0-9a-f]+)$', constants, re.M)
        if len(matches) != 1:
            raise ValueError('missing or ambiguous scheduler source ' + name)
        value = int(matches[0], 16) + 0x1000
        constants = re.sub(r'^' + name + r' = \$[0-9a-f]+$',
                           f'{name} = ${value:04x}', constants, flags=re.M)
    prefix = module.ljust(HEADER - CORE, b'\0') + identity(module)
    return (CORE.to_bytes(2, 'little') +
            prefix.ljust(SCHEDULER_SOURCE - CORE, b'\0') + payload[2:], constants)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    config = sub.add_parser('config')
    config.add_argument('enabled', choices=('0', '1'))
    config.add_argument('output', type=Path)
    generate = sub.add_parser('bindings')
    generate.add_argument('module', type=Path)
    generate.add_argument('gateway', type=Path)
    generate.add_argument('map', type=Path)
    generate.add_argument('output', type=Path)
    layout = sub.add_parser('layout')
    layout.add_argument('normal', type=Path)
    layout.add_argument('panic', type=Path)
    layout.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.action == 'config':
        write_changed(args.output, (json.dumps({'window_cache': int(args.enabled)}) + '\n').encode())
    elif args.action == 'layout':
        result = layout_maps(args.normal.read_text(), args.panic.read_text())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    else:
        acceptance, loader = bindings(args.module.read_bytes(), args.gateway.read_bytes(), args.map.read_text())
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'acceptance.inc').write_text(acceptance)
        (args.output / 'loader.inc').write_text(loader)


if __name__ == '__main__':
    main()

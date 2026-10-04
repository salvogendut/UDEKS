#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check the four-graphics-app layout against actual build artifacts.

This is a placement gate; live execution is qualified separately by the probes.
All intervals are half-open physical-bank ranges; boot-only source padding
is never treated as a permanent allocation.
"""
import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re

from build_scheduler_overlay import map_segments
from ihx_to_bin import read_ihx
from build_window_cache import glyph_overlay_layout
from gen_capability_imports import map_exports

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Region:
    name: str
    bank: int
    start: int
    limit: int


# Fixed banked allocations. The existing common-RAM,
# native foreground child, shell and display/cache reservations stay intact.
CANDIDATE = (
    Region('banked app 3 image+BSS', 1, 0x2300, 0x3500),
    Region('banked app 4 image+BSS', 1, 0x3500, 0x4000),
    Region('app 3 software stack reservation', 1, 0x8A00, 0x8D00),
    Region('app 4 software stack reservation', 1, 0x8D00, 0x9000),
    Region('app 3 relocated zero page/hardware stack', 1, 0xD500, 0xD700),
    Region('app 4 relocated zero page/hardware stack', 1, 0xD700, 0xD900),
)


def disjoint(regions):
    for r in regions:
        if r.bank not in (0, 1) or not 0 <= r.start < r.limit <= 0x10000:
            raise ValueError('invalid region: ' + r.name)
        # This machine exposes bank 0, not bank 1, in upper common RAM.
        if r.bank == 1 and r.limit > 0xF000:
            raise ValueError('bank-1 region reaches common RAM: ' + r.name)
    ordered = sorted(regions, key=lambda r: (r.bank, r.start, r.limit))
    for left, right in zip(ordered, ordered[1:]):
        if left.bank == right.bank and left.limit > right.start:
            raise ValueError('overlap: ' + left.name + ' / ' + right.name)


def z80_regions(text):
    """Read ALL linked SDCC area sizes, including initially empty data areas.

    The global s__/l__ pairs describe zero-sized areas omitted from the area
    tables. Unknown nonempty areas also participate in the collision check.
    """
    symbols = {}
    for value, kind, name in re.findall(
            r'^\s*([0-9A-Fa-f]{8})\s+([sl])__(\w+)\s*$', text, re.M):
        key = (kind, name)
        number = int(value, 16)
        if key in symbols and symbols[key] != number:
            raise ValueError('conflicting Z80 area symbol')
        symbols[key] = number
    if symbols.get(('s', 'CODE')) != 0x2000 or not symbols.get(('l', 'CODE')):
        raise ValueError('missing Z80 code bounds')
    names = {name for _, name in symbols}
    regions = []
    for name in sorted(names):
        if ('s', name) not in symbols or ('l', name) not in symbols:
            raise ValueError('incomplete Z80 area bounds: ' + name)
        start, size = symbols['s', name], symbols['l', name]
        if size:
            regions.append(Region('Z80 ' + name, 1, start, start + size))
    disjoint(regions)
    return regions


def managed_size(data):
    if len(data) < 34 or data[:8] != b'UDEX\x00\x01\x01\x02':
        raise ValueError('expected managed UDEX 0.1')
    load, size, bss, entry = (int.from_bytes(data[n:n+2], 'little')
                              for n in (8, 10, 12, 14))
    if len(data) != size + 16 or entry != load or load + size + bss > 65536:
        raise ValueError('invalid managed image length/entry/allocation')
    for n in range(16, 34, 3):
        target = int.from_bytes(data[n+1:n+3], 'little')
        if data[n] != 0x4C or not load + 18 <= target < load + size:
            raise ValueError('invalid managed callback')
    return {'load': load, 'image': size, 'bss': bss, 'allocation': size + bss}


def worker_image(regions, image, padded):
    if len(padded) != 0x2000:
        raise ValueError('Z80 output container changed')
    for address, value in image.items():
        if not any(r.start <= address < r.limit for r in regions):
            raise ValueError('Z80 emitted byte outside measured areas')
        if not 0x2000 <= address < 0x4000 or padded[address-0x2000] != value:
            raise ValueError('Z80 map/HEX/container mismatch')
    for offset, value in enumerate(padded):
        if value != image.get(0x2000+offset, 0):
            raise ValueError('Z80 container has unaccounted data')


def source_value(path, name):
    text = (ROOT / path).read_text()
    values = re.findall(r'^' + re.escape(name) + r'\s*=\s*\$([0-9a-fA-F]+)\s*$', text, re.M)
    if len(values) != 1:
        raise ValueError('missing/ambiguous source binding: ' + name)
    return int(values[0], 16)


def check_reservations():
    text = (ROOT / 'include/udeks/memory.h').read_text()
    expected = dict(UDEKS_TASK_BACKUP_BASE=0x8000, UDEKS_TASK_BACKUP_LIMIT=0x8A00,
                    UDEKS_USH_BASE=0x9000, UDEKS_USH_LIMIT=0xA000,
                    UDEKS_BOOTFS_BASE=0xA000, UDEKS_BOOTFS_LIMIT=0xB000,
                    UDEKS_Z80_CODE_BASE=0x2000, UDEKS_Z80_CODE_LIMIT=0x4000,
                    UDEKS_VIC_WINDOW_BASE=0x4000, UDEKS_VIC_WINDOW_LIMIT=0x8000,
                    UDEKS_COMMON_BASE=0xF000)
    for name, value in expected.items():
        matches = re.findall(r'^#define\s+' + name + r'\s+0x([0-9a-fA-F]+)u\s*$', text, re.M)
        if len(matches) != 1 or int(matches[0], 16) != value:
            raise ValueError('memory reservation changed: ' + name)
    if source_value('src/scheduler/task_yield_handler.s', 'TASK2_STACK_BOTTOM') != 0xC00 or \
            source_value('src/scheduler/task_yield_handler.s', 'TASK2_STACK_TOP') != 0x1200:
        raise ValueError('native foreground stack changed')


def baseline_regions(kernel, storage, worker):
    # Using complete reservations avoids treating slack in a running service
    # as an allocation. Validate the emitted map before accepting each bound.
    regions = [Region('kernel pages', 0, 0, 0x200),
               Region('legacy clock slot', 0, 0x200, 0xC00),
               Region('banked graphics service', 0, 0xC00, 0x1200),
               Region('legacy wave slot', 0, 0x1200, 0x1C00),
               Region('scheduler page', 0, 0x1C00, 0x2000),
               Region('resident and scheduler tail', 0, 0x2000, 0xD000),
               Region('resident high state and C stack', 0, 0xE000, 0xF000),
               Region('common RAM', 0, 0xF000, 0x10000),
               Region('native child and disk staging/stack', 1, 0, 0x1200),
               Region('storage module', 1, 0x1200, 0x1880),
               Region('relocation module', 1, 0x1880, 0x1A00),
               Region('task lookup module', 1, 0x1A00, 0x1F00),
               Region('banked access module', 1, 0x1F00, 0x2000),
               Region('display/cache/bitmap/sprite', 1, 0x4000, 0x8000),
               Region('legacy foreground backup', 1, 0x8000, 0x8A00),
               Region('ush', 1, 0x9000, 0xA000),
               Region('recovery bootfs', 1, 0xA000, 0xB000),
               Region('filesystem policy', 1, 0xB000, 0xC600),
               Region('banked image loader', 1, 0xD900, 0xE000),
               Region('service state/context/driver and ush stack', 1, 0xE000, 0xF000)]
    allowed = {'ZEROPAGE', 'STARTUP', 'CODE', 'RODATA', 'DATA', 'BSS', 'STORAGECODE', 'IECCODE'}
    if storage.keys() != allowed:
        raise ValueError('storage segments changed; review ownership')
    for name, low, high in (
            ('STARTUP', 0x1200, 0x1880), ('CODE', 0x1200, 0x1880),
            ('RODATA', 0x1200, 0x1880), ('DATA', 0x1200, 0x1880),
            ('BSS', 0xE000, 0xE180), ('STORAGECODE', 0xB000, 0xC600),
            ('IECCODE', 0xE300, 0xE900)):
        start, end, size = storage[name]
        if not low <= start <= end < high or size != end - start + 1:
            raise ValueError('storage reservation changed: ' + name)
    for name in ('CODE', 'RODATA', 'DATA', 'BSS'):
        if not 0x2000 <= kernel[name][0] <= kernel[name][1] < 0x96A8:
            raise ValueError('resident reaches boot assets: ' + name)
    for path, prefix in (('src/scheduler/task_context.s', 'TASK'),
                         ('src/scheduler/task_yield_handler.s', 'TASK2')):
        page0 = source_value(path, prefix + '_PAGE0')
        page1 = source_value(path, prefix + '_PAGE1')
        bank = source_value(path, prefix + '_PAGE_BANK')
        regions.extend((Region(prefix + ' zero page', bank, page0*256, (page0+1)*256),
                        Region(prefix + ' hardware stack', bank, page1*256, (page1+1)*256)))
    return regions + worker


def graphics_lifetimes(regions):
    phases = {
        'before_first_native_launch': [Region('base graphics delivery',1,0xc600,0xcc00),
                                      Region('paths delivery',1,0xcc00,0xd000)],
        'after_both_modules_installed': [Region('client 3 retained image',1,0xc600,0xcb00),
                                         Region('client 4 retained image',1,0xcb00,0xd000)],
    }
    for additions in phases.values():
        disjoint(regions + additions)
    return {name:[asdict(r) for r in additions] for name,additions in phases.items()}


def glyph_overlay_images(assets, paths, kernel, delivery):
    if len(assets)!=1112 or assets[:6]!=b'VTG1\x01\x3f':
        raise ValueError('expected exactly 63 uploaded 16-byte custom glyphs')
    if kernel[0x96a8-0x2000:0x9b00-0x2000]!=assets:
        raise ValueError('kernel glyph delivery does not match boot assets')
    if len(paths)!=1008:
        raise ValueError('paths output must fit exactly the uploaded glyph bytes')
    offset=2+0xcc00-0x1200
    if delivery[:2]!=b'\0\x12' or delivery[offset:offset+1008]!=paths:
        raise ValueError('paths secondary delivery differs')


def glyph_overlay_entrypoints(segments,exports):
    start,end,_=segments['GRAPHICSPATHS']
    for name in ('_udeks_retained_present','_udeks_retained_paths_paint'):
        if name not in exports or not start<=exports[name][0]<=end:
            raise ValueError('paths entry is outside executable code: '+name)


def audit(build):
    check_reservations()
    normal = map_segments((build / '8502/udeks-8502.map').read_text())
    panic = map_segments((build / '8502/udeks-8502-panic-probe.map').read_text())
    if normal != panic:
        raise ValueError('normal/panic placement differs')
    storage = map_segments((build / 'storage/module.map').read_text())
    worker = z80_regions((build / 'z80/udeks-z80.map').read_text())
    regions = baseline_regions(normal, storage, worker)
    phases=graphics_lifetimes(regions + list(CANDIDATE))
    glyph_overlay_layout(normal)
    glyph_overlay_entrypoints(normal,map_exports((build/'8502/udeks-8502.map').read_text()))
    paths=(build/'8502/retained-paths.bin').read_bytes()
    if paths!=(build/'8502/retained-paths-panic.bin').read_bytes():
        raise ValueError('normal/panic paths modules differ')
    delivery=(build/'boot/scheduler-overlay.prg').read_bytes()
    glyph_overlay_images((build/'assets/udeks-vdc-text.bin').read_bytes(),paths,
                         (build/'8502/udeks-8502.bin').read_bytes(),delivery)
    worker_image(worker, read_ihx(build / 'z80/udeks-z80.ihx'),
                 (build / 'z80/udeks-z80.bin').read_bytes())
    if not 0 < (build / 'boot/task-lookup.bin').stat().st_size <= 0x500:
        raise ValueError('task lookup exceeds its reservation')
    loader = (build / 'boot/banked-loader.bin').read_bytes()
    segments = map_segments((build / 'boot/banked-loader.map').read_text())
    if (loader[:1] != b'\x4c' or loader[3:9] != b'BLOD\0\1' or
            not 9 < len(loader) <= 0x700 or
            segments.get('CODE') != (0xD900, 0xD900+len(loader)-1, len(loader))):
        raise ValueError('banked loader exceeds its reservation or identity/map differs')
    if set(segments)!={'CODE','RELOC','ACCESS'}:
        raise ValueError('banked loader segment set changed')
    for name,address,capacity,filename,magic in (
            ('RELOC',0x1880,0x180,'banked-reloc.bin',b'BREL\0\1'),
            ('ACCESS',0x1f00,0x100,'banked-access.bin',b'BACC\0\1')):
        blob=(build/('boot/'+filename)).read_bytes()
        if (blob[:1]!=b'\x4c' or blob[3:9]!=magic or not 9<len(blob)<=capacity or
                segments.get(name)!=(address,address+len(blob)-1,len(blob))):
            raise ValueError('banked extension reservation or identity/map differs: '+name)
    for name,low,limit in (('GRAPHICSCODE',0xC00,0x1200),('GRAPHICSHELP',0xA100,0xA1E0)):
        start,end,size=normal[name]
        if not (start == low and size == end - start + 1 and end < limit):
            raise ValueError('graphics module placement changed: '+name)
    module=(build/'8502/banked-graphics.bin').read_bytes()
    if len(module)!=0x600 or module != (build/'8502/banked-graphics-panic.bin').read_bytes():
        raise ValueError('graphics module outputs differ or exceed reservation')
    offset=2+0xc600-0x1200
    if delivery[offset:offset+len(module)]!=module:
        raise ValueError('base graphics secondary delivery differs')
    apps = {name: managed_size((build / ('user/' + name + '.udx')).read_bytes())
            for name in ('xclock', 'xwave')}
    from build_d71 import validate_banked_app
    for name,base,capacity in (('xcalc',0x2300,0x1200),('xdraw',0x3500,0xB00)):
        program=(build/('user/'+name+'.udx')).read_bytes()
        validate_banked_app(program,base,capacity)
        load,image,bss,entry=(int.from_bytes(program[n:n+2],'little') for n in (8,10,12,14))
        apps[name]=dict(load=load,image=image,bss=bss,allocation=image+bss)
    for name, load, capacity in (('xclock', 0x200, 0xA00), ('xwave', 0x1200, 0xA00),
                                  ('xcalc', 0x2300, 0x1200), ('xdraw', 0x3500, 0xB00)):
        if apps[name]['load'] != load or apps[name]['allocation'] > capacity:
            raise ValueError('baseline app placement changed: ' + name)
    inputs = ['8502/udeks-8502.map', '8502/udeks-8502-panic-probe.map',
              'storage/module.map', 'z80/udeks-z80.map', 'z80/udeks-z80.bin', 'z80/udeks-z80.ihx',
              'boot/task-lookup.bin', 'boot/banked-loader.bin',
              'boot/banked-loader.map', 'boot/banked-reloc.bin', 'boot/banked-access.bin', '8502/banked-graphics.bin',
              '8502/retained-paths.bin','assets/udeks-vdc-text.bin','boot/scheduler-overlay.prg',
              '8502/banked-graphics-panic.bin'] + ['user/' + n + '.udx' for n in apps]
    return dict(status='four independent graphical executables; placement verified',
                baseline_apps=apps,
                proposed=[asdict(r) for r in CANDIDATE],
                existing=[asdict(r) for r in regions],
                calculator_current_allocation_spare=0x1200-apps['xcalc']['allocation'],
                fourth_app_capacity=0xB00,
                fourth_app_allocation_spare=0xB00-apps['xdraw']['allocation'],
                private_stack_reservation_per_banked_app=0x300,
                resident_bridge_headroom=0x96A8-normal['BSS'][1]-1,
                graphics_delivery_and_retention_lifetimes=phases,
                glyph_overlay=dict(start=0x96b8,bytes=1008,live_header=16,live_tile_maps=88),
                source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                               for p in ('include/udeks/memory.h', 'src/scheduler/task_context.s',
                                         'src/scheduler/task_yield_handler.s', 'tools/graphics_app_layout.py',
                                         'src/services/app/banked_loader.s', 'src/boot/stage1-gateway.s',
                                         'src/services/window/banked_graphics.c',
                                         'src/services/window/banked_access.s',
                                         'src/services/window/retained_paths.c',
                                         'include/udeks/retained_paths.h',
                                          'user/bin/xcalc_native.c', 'user/bin/xdraw.c',
                                          'user/lib/graphics_request.s')},
                input_sha256={p: hashlib.sha256((build / p).read_bytes()).hexdigest() for p in inputs})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT / 'build')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.build)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, 'four-app placement rejected: ' + str(error) + '\n')
    data = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data)
    print(data, end='')


if __name__ == '__main__':
    main()

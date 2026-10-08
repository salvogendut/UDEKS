#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify actual default normal/panic links and their disk service files."""
import hashlib
import json
from pathlib import Path

import build_d71 as d71
import build_d81 as d81
from build_time_overlay import qualify
from build_window_cache import layout_maps
from gen_capability_imports import map_exports
from placement_audit import parse_map
from service_image import validate

ROOT = Path(__file__).resolve().parents[1]


def layouts(normal, panic, binaries):
    if len(binaries) != 2:
        raise ValueError('both normal and panic binaries are required')
    # This independent guard pins ALL app/stack/VIC/VDC/common/ZP reservations,
    # verifies normal/panic parity and bounds each flexible resident segment.
    segments = layout_maps(normal, panic)
    if 'SERVICEBOOT' not in segments:
        raise ValueError('normal boot lacks service startup overlay')
    result = {}
    for label, text, image in zip(('normal','panic'),(normal,panic),binaries):
        modules, _ = parse_map(text)
        if 'time.o' in modules:
            raise ValueError('resident time implementation is still linked')
        for name in ('time-slot.o','time-resident.o','service_registry.o'):
            if name not in modules:
                raise ValueError('missing default service object: '+name)
        # qualify checks code/data separation, emitted JMP operands and the
        # absence of the extracted setter, after the frozen-layout guard above.
        result[label] = qualify({k:v for k,v in segments.items() if k!='SERVICEBOOT'},
                                segments,map_exports(text),image)
    return result


def layout_report(root):
    texts = [(root/f'build/8502/udeks-8502{s}.map').read_text() for s in ('','-panic-probe')]
    images = [(root/f'build/8502/udeks-8502{s}.bin').read_bytes() for s in ('','-panic-probe')]
    return dict(variants=layouts(*texts,images),
                module=validate((root/'build/services/time/TIME.SVC').read_bytes()))


def disk_files(data, fmt):
    offset,track,sector = (d81.sector_offset,40,3) if fmt=='d81' else (d71.sector_offset,18,1)
    result = {}
    for entry in d81.entries(data,offset,track,sector):
        name = entry[3:19].rstrip(b'\xa0').decode('ascii')
        if name in result:
            raise ValueError('duplicate disk name: '+name)
        result[name] = (entry[0],d81.file_bytes(data,entry,offset))
    return result


def build_report(root):
    result = dict(source=str(root),scope='normal disk-service boot; emulator tests separate',
                  **layout_report(root),disks={})
    expected = {'TIME.SVC':(0x81,(root/'build/services/time/TIME.SVC').read_bytes()),
                'SVC.BIN':(0x81,(root/'build/services/command/SVC.BIN').read_bytes()),
                'RC.ETC':(0x81,(root/'user/etc/rc').read_bytes())}
    for fmt in ('d64','d71','d81'):
        path = root/f'build/boot/udeks.{fmt}'
        data = path.read_bytes()
        files = disk_files(data,fmt)
        if any(files.get(n)!=v for n,v in expected.items()):
            raise ValueError('missing or stale service/RC disk file: '+fmt)
        if ('XSPRDEF.BIN' in files) != (fmt!='d64'):
            raise ValueError('wrong optional-app disk selection: '+fmt)
        result['disks'][fmt] = dict(path=str(path),sha256=hashlib.sha256(data).hexdigest())
    return result


def main():
    report = layout_report(ROOT)
    output = ROOT/'build/services/time/default-layout.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()

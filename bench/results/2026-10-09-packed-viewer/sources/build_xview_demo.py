#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Package the packed-picture viewer demo without altering published disks.

Build matching boot candidates and XVIEW first. Uses a new output directory,
preserves every existing disk file, and leaves the full compact D64 alone.
"""
import argparse
import hashlib
import json
from pathlib import Path
from add_cbm_viewer import add_viewer
from png_to_cbm import convert
from storage_public_probe import files

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/xview/demo')
    args=parser.parse_args();out=args.output.resolve()
    if out.exists():parser.error('choose a new output directory')
    out.mkdir(parents=True)
    pictures=[]
    for name in ('ALEX','CLOCKWORK','ALEX2'):
        data=(ROOT/'PICS'/(name+'.CBM')).read_bytes()
        (out/(name+'.CBM')).write_bytes(data);pictures.append((name+'.CBM',data))
    for source,name,width,height in (('alex.png','ALEX128',128,80),('clockwork.png','CLOCK160',160,100)):
        target=out/(name+'.CBM');convert(ROOT/'PICS'/source,target,width,height,128,False,True)
        pictures.append((target.name,target.read_bytes()))
    digest=lambda data:hashlib.sha256(data).hexdigest()
    app=(ROOT/'build/xview/XVIEW.BIN').read_bytes()
    report=dict(abi_minor=20,app_sha256=digest(app),pictures={n:digest(d) for n,d in pictures},disks={})
    for fmt in ('d71','d81'):
        original=(ROOT/'build/boot'/('udeks.'+fmt)).read_bytes()
        disk=add_viewer(original,app,pictures);target=out/('udeks-packed.'+fmt);target.write_bytes(disk)
        before=files(original);after=files(disk)
        if any(after.get(name)!=data for name,data in before.items()):
            raise ValueError('demo changed an existing file')
        report['disks'][fmt]=dict(base_sha256=digest(original),sha256=digest(disk),
            original_files={name.decode('ascii'):digest(data) for name,data in before.items()})
        print(target)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()

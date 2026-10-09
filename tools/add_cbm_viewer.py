#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install independent XVIEW.BIN and .CBM pictures on a NEW disk-image copy."""
import argparse
from pathlib import Path
import re

from add_disk_apps import add_apps, directory_names
from build_d71 import install_prg_file, D64_SIZE
import build_d81
from png_to_cbm import parse


def add_viewer(image, app, pictures):
    result=bytearray(add_apps(image,[('XVIEW.BIN',app)]))
    names=directory_names(result)
    for name,data in pictures:
        name=name.upper()
        if not re.fullmatch(r'[A-Z0-9_-]{1,12}\.CBM',name):
            raise ValueError('picture name must be 1..12 letters/digits/_/- followed by .CBM')
        key=name.encode('ascii')
        if key in names: raise ValueError('disk filename already exists: '+name)
        parse(data)
        names.add(key)
        if len(result)==build_d81.SIZE:
            build_d81.install_file(result,name,data,file_type=0x81)
        else:
            install_prg_file(result,name,data,file_type=0x81,
                             max_track=35 if len(result)==D64_SIZE else 70)
    return bytes(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--app',type=Path,default=Path('build/xview/XVIEW.BIN'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('pictures',nargs='+',type=Path)
    args=parser.parse_args()
    if args.output.exists() or args.output.is_symlink(): parser.error('output already exists; choose a new image')
    try:
        data=add_viewer(args.disk.read_bytes(),args.app.read_bytes(),
            [(p.name,p.read_bytes()) for p in args.pictures])
        with args.output.open('xb') as out: out.write(data)
    except (OSError,ValueError) as error: parser.error(str(error))
    print('Created',args.output,'without rebuilding or changing the kernel')


if __name__=='__main__': main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private DOS mutation backend on generated disposable media only.

Not a UDEKS public-command or namespace qualification. No input disk option:
all source, destination and KEEP files are created exclusively for this test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import build_d81 as d81
from build_d71 import blank_d71, d64_compatibility_image, install_prg_file, sector_offset

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {'KEEP': (0x81, bytes(range(255,-1,-1))*3),
           'SRCSEQ': (0x81, bytes(range(256))*3),
           'SRCPRG': (0x82, b'\0\x0e'+bytes(range(256))*2),
           'LONGSOURCE123456': (0x82, b'\0\x0e'+bytes(range(256))*2),
           'EMPTY': (0x81, b'')}


def read_files(image, drive):
    offset, directory = (d81.sector_offset, (40,3)) if drive=='1581' else (sector_offset, (18,1))
    result = {}
    for entry in d81.entries(image, offset, *directory):
        name = entry[3:19].rstrip(b'\xa0').decode('ascii')
        if entry[0] not in (0x81,0x82) or name in result:
            raise AssertionError(('invalid/duplicate entry',name,entry.hex()))
        result[name] = (entry[0],d81.file_bytes(image,entry,offset))
    return result


def fixture(drive):
    image = d81.blank_d81(name=b'MUTATE PROBE') if drive=='1581' else blank_d71()
    for name,(kind,data) in SAMPLES.items():
        if drive=='1581': d81.install_file(image,name,data,file_type=kind)
        else: install_prg_file(image,name,data,file_type=kind)
    return bytes(d64_compatibility_image(image) if drive=='1541' else image)


def run(drive):
    base=ROOT/'build/storage-file-commands/mutate';base.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix=drive+'-',dir=base))
    disk=work/('disposable.'+{'1541':'d64','1571':'d71','1581':'d81'}[drive])
    original=fixture(drive);disk.write_bytes(original)
    (work/('before'+disk.suffix)).write_bytes(original)
    program=work/'mutate.prg'
    program.write_bytes((ROOT/'build/bench/iec-mutate/mutate.prg').read_bytes())
    assert read_files(original,drive)==SAMPLES
    phases=[]
    for ro in (1,0):
        tag='protected' if ro else 'mutated'
        raw=work/(tag+'.bin')
        command=['python3','tools/vice_capture.py',str(program),str(raw),
                 '--raw-load','--entry','0x2800','--result-address','0x6000',
                 '--result-size','0x60','--state-offset','0','--complete-value','2',
                 '--timeout','120','--poll-delay','2','--capture-incomplete',
                 '--poke',f'0x60f0={ro}','--vice-arg=-drive8truedrive',
                 '--vice-arg=-drive8type','--vice-arg='+drive,
                 '--vice-arg=-8','--vice-arg='+str(disk)]
        if ro: command.append('--vice-arg=-attach8ro')
        with (work/(tag+'.log')).open('w') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        record=raw.read_bytes() if raw.exists() else b''
        if result.returncode or len(record)!=96 or record[0]!=2:
            raise AssertionError((drive,tag,record.hex(),str(work)))
        actual=read_files(disk.read_bytes(),drive)
        if ro:
            assert disk.read_bytes()==original
            assert record[1:4]==bytes((1,30,30))
        else:
            assert record[1:4]==bytes((11,0,0))
            expected=SAMPLES|{'COPYPRG':SAMPLES['SRCPRG'],'COPYEMPTY':SAMPLES['EMPTY'],
                              'LONG1234567890AB':SAMPLES['SRCPRG']}
            if actual!=expected: raise AssertionError((drive,'on-disk type/bytes',actual.keys(),str(work)))
        phases.append(dict(phase=tag,record=record.hex(),
                           disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest()))
        print('PASS',drive,tag,'exact files/types, source and KEEP preserved',flush=True)
    (work/'result.json').write_text(json.dumps(dict(drive=drive,phases=phases,
        scope='private backend; namespace/permission preflight and public commands not installed',
        empty_copy='known-empty SEQ fixture uses exclusive create plus checked close, not DOS COPY',
        program_sha256=hashlib.sha256(program.read_bytes()).hexdigest(),
        before_sha256=hashlib.sha256(original).hexdigest()),indent=2)+'\n')
    print('Evidence:',work,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--drive',choices=('1541','1571','1581','all'),default='all')
    args=parser.parse_args()
    for drive in (('1541','1571','1581') if args.drive=='all' else (args.drive,)): run(drive)


if __name__=='__main__': main()

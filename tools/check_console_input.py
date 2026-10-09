#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute the production 6502 reader/ownership adapter, with negative control."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'build/native-console/input-cpu'; out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').unlink(missing_ok=True)
    def run(*args): subprocess.run(args,cwd=ROOT,check=True)
    cfg=Path('/usr/share/cc65/cfg/sim6502.cfg').read_text()
    (out/'test.cfg').write_text(cfg.replace('SEGMENTS {','SEGMENTS {\n MODULECODE: load=MAIN,type=ro;'))
    run('ca65','-o',str(out/'reader.o'),'src/8502/line_editor_read.s')
    run('cl65','-t','sim6502','-Oirs','-I','include','-c','-o',str(out/'check.o'),
        'bench/native-console/input_check.c')
    def check(name,reader):
        run('cl65','-t','sim6502','-C',str(out/'test.cfg'),'-o',str(out/(name+'.sim65')),
            str(out/'check.o'),str(reader))
        result=subprocess.run(['sim65',str(out/(name+'.sim65'))],text=True,capture_output=True,timeout=60)
        (out/(name+'.log')).write_text(result.stdout+result.stderr)
        print(result.stdout+result.stderr,end='')
        return result
    check('positive',out/'reader.o').check_returncode()
    source=(ROOT/'src/8502/line_editor_read.s').read_text()
    if source.count('bne input_denied')!=3: raise ValueError('ownership branches changed')
    (out/'negative.s').write_text(source.replace('bne input_denied','nop\n        nop',1))
    run('ca65','-o',str(out/'negative.o'),str(out/'negative.s'))
    result=check('negative',out/'negative.o')
    if not result.returncode or 'FAIL owner' not in result.stdout:
        raise AssertionError('negative control did not catch stolen input')
    print('PASS negative control: background ownership bypass rejected')
    (out/'report.json').write_text(json.dumps(dict(ownership_cases=2048,reader_cases=6270,
        negative_control='background ownership bypass rejected',scope='6502 adapter, query stub; no MMU'),indent=2)+'\n')


if __name__=='__main__': main()

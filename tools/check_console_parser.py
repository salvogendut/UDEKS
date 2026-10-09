#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Differential-test the production tokenizer against its C reference on 6502."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'build/native-console/parser'; out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').unlink(missing_ok=True)
    def run(*args): subprocess.run(args,cwd=ROOT,check=True)
    # Add only placement of MODULECODE; both production and reference sources
    # keep their real instructions/calling convention, linked with sim runtime.
    cfg=Path('/usr/share/cc65/cfg/sim6502.cfg').read_text()
    if cfg.count('SEGMENTS {')!=1: raise ValueError('unexpected sim6502 config')
    (out/'test.cfg').write_text(cfg.replace('SEGMENTS {','SEGMENTS {\n    MODULECODE: load=MAIN, type=ro;\n    CLIENTENTRY: load=MAIN,type=ro,optional=yes;'))
    run('ca65','--cpu','6502','-o',str(out/'parser.o'),'src/services/shell/parser.s')
    run('cl65','-t','sim6502','-Oirs','-I','include','-Dudeks_shell_tokenize=reference_tokenize',
        '-c','-o',str(out/'reference.o'),'user/lib/shell_parser.c')
    run('cl65','-t','sim6502','-Oirs','-I','include','-c','-o',str(out/'check.o'),
        'bench/native-console/parser_check.c')
    run('cl65','-t','sim6502','-C',str(out/'test.cfg'),'-o',str(out/'check.sim65'),
        str(out/'parser.o'),str(out/'reference.o'),str(out/'check.o'))
    result=subprocess.run(['sim65',str(out/'check.sim65')],text=True,capture_output=True,timeout=60)
    (out/'check.log').write_text(result.stdout+result.stderr)
    print(result.stdout+result.stderr,end=''); result.check_returncode()
    # A real regression in the candidate must be caught, not only source text.
    source=(ROOT/'src/services/shell/parser.s').read_text()
    if source.count('cmp #9')!=2: raise ValueError('tokenizer comparisons moved')
    (out/'negative.s').write_text(source.replace('cmp #9','cmp #10'))
    run('ca65','--cpu','6502','-o',str(out/'negative.o'),str(out/'negative.s'))
    run('cl65','-t','sim6502','-C',str(out/'test.cfg'),'-o',str(out/'negative.sim65'),
        str(out/'negative.o'),str(out/'reference.o'),str(out/'check.o'))
    negative=subprocess.run(['sim65',str(out/'negative.sim65')],text=True,capture_output=True,timeout=60)
    (out/'negative.log').write_text(negative.stdout+negative.stderr)
    if not negative.returncode or 'FAIL tokenizer' not in negative.stdout:
        raise AssertionError('tokenizer negative control was not detected')
    print('PASS negative control: incorrect tab splitting rejected')
    # Same entry instructions, placed after the simulator's own startup.
    entry=(ROOT/'user/lib/native_console_entry.s').read_text()
    if entry.count('.segment "STARTUP"')!=1: raise ValueError('entry segment changed')
    (out/'entry.s').write_text(entry.replace('.segment "STARTUP"','.segment "CLIENTENTRY"'))
    run('ca65','-I','src/8502','-o',str(out/'entry.o'),str(out/'entry.s'))
    run('ca65','-I','src/8502','-o',str(out/'copy.o'),'bench/native-console/args_copy.s')
    run('cl65','-t','sim6502','-Oirs','-I','include','-c','-o',str(out/'entry-check.o'),
        'bench/native-console/entry_check.c')
    run('cl65','-t','sim6502','-C',str(out/'test.cfg'),'-o',str(out/'entry.sim65'),
        str(out/'entry.o'),str(out/'copy.o'),str(out/'parser.o'),str(out/'entry-check.o'))
    entry_result=subprocess.run(['sim65',str(out/'entry.sim65')],text=True,capture_output=True,timeout=60)
    (out/'entry.log').write_text(entry_result.stdout+entry_result.stderr)
    print(entry_result.stdout+entry_result.stderr,end=''); entry_result.check_returncode()
    report=dict(scope='production 6502 tokenizer vs C reference; no MMU emulation',
        comparisons=11520,negative_control='incorrect tab splitting rejected',
        argument_entry=True,inputs={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ('src/services/shell/parser.s','user/lib/shell_parser.c','bench/native-console/parser_check.c',
             'src/8502/native_args.inc','src/8502/native_args_copy.inc','user/lib/native_console_entry.s',
             'bench/native-console/args_copy.s','bench/native-console/entry_check.c')})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__': main()

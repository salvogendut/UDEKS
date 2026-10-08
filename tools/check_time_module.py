#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute the sealed time module under sim6502 (RAM-backed CIA registers)."""
from pathlib import Path
import subprocess
from service_image import seal, validate

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT/'build/services/time'
    image = out/'TIME.SVC'
    data=image.read_bytes()
    record=validate(data)
    def run(*cmd, **kwargs):
        return subprocess.run(cmd, cwd=ROOT, check=True, **kwargs)
    (out/'embed.s').write_text('.export _module_image\n.segment "RODATA"\n'
                              '_module_image:\n.incbin "build/services/time/TIME.SVC"\n')
    objects = []
    for name, path in (('check', ROOT/'bench/time-module/check.c'),
                       ('call', ROOT/'bench/time-module/call.s'),
                       ('embed', out/'embed.s')):
        obj = out/(name+'.o')
        run('cl65', '-t', 'sim6502', '-Oirs', '-c', '-o', str(obj), str(path))
        objects.append(str(obj))
    run('cl65', '-t', 'sim6502', '-m', str(out/'check.map'),
        '-o', str(out/'check.sim65'), *objects)
    proof = subprocess.run(['sim65', str(out/'check.sim65')], cwd=ROOT,
                           capture_output=True, text=True, timeout=60)
    (out/'check.log').write_text(proof.stdout+proof.stderr)
    print(proof.stdout, end='')
    print(proof.stderr, end='')
    proof.check_returncode()
    # Verify that this harness really executes the supplied module, rather
    # than a linked resident implementation or a C model. Let hour 24 through
    # the first range check; the unchanged independent oracle must reject it.
    negative=bytearray(data)
    offset=record['request']-record['base']
    if negative[offset:offset+2] != b'\xc9\x18':
        raise ValueError('negative-control instruction changed; requalify it')
    negative[offset+1]=25
    (out/'negative.SVC').write_bytes(seal(negative))
    (out/'embed.s').write_text('.export _module_image\n.segment "RODATA"\n'
                              '_module_image:\n.incbin "build/services/time/negative.SVC"\n')
    run('ca65','-o',str(out/'negative-embed.o'),str(out/'embed.s'))
    run('cl65','-t','sim6502','-o',str(out/'negative.sim65'),
        *objects[:2],str(out/'negative-embed.o'))
    failed=subprocess.run(['sim65',str(out/'negative.sim65')],cwd=ROOT,
                          capture_output=True,text=True,timeout=60)
    (out/'negative.log').write_text(failed.stdout+failed.stderr)
    if not failed.returncode or 'FAIL invalid-hour rejection (negative control)' not in failed.stdout:
        raise AssertionError('negative control did not fail for the injected instruction')
    print('PASS negative control: altered module instruction detected')


if __name__ == '__main__': main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Link the time service independently, without a kernel map/import bridge."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from service_image import seal, validate

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/services/time')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    # Generated outputs only: a failed build cannot leave a stale success.
    for name in ('TIME.SVC', 'layout.json', 'time.map', 'time.bin'):
        (out/name).unlink(missing_ok=True)

    def run(*command):
        subprocess.run(command, cwd=ROOT, check=True)

    # Nonrecursive, serialized service entries may use image-owned scratch.
    # Its BSS is charged to the module, never to the kernel or an app slot.
    run('cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Oirs',
        '--static-locals', '-D', 'UDEKS_TIME_MODULE', '-I', 'include',
        '-o', str(out/'time.s'), 'src/services/time/time.c')
    objects = []
    for name, source in (('module', ROOT/'src/services/time/module.s'),
                         ('runtime', ROOT/'src/services/time/runtime.s'),
                         ('time', out/'time.s')):
        obj = out/(name+'.o')
        run('ca65', '--cpu', '6502', '-I', 'src/services/time',
            '-o', str(obj), str(source))
        objects.append(str(obj))
    run('cl65', '-t', 'none', '--cpu', '6502', '-C', 'cfg/8502-time-module.cfg',
        '-m', str(out/'time.map'), '-o', str(out/'time.bin'), *objects)
    image = seal((out/'time.bin').read_bytes())
    (out/'TIME.SVC').write_bytes(image)
    report = validate(image)
    report['sha256'] = hashlib.sha256(image).hexdigest()
    report['scope'] = 'independent module candidate; not installed in normal boot'
    (out/'layout.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

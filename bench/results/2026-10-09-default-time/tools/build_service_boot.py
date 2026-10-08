#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproduce normal disk-service boot from fresh, isolated source copies.

The ordinary Make dependency graph regenerates EVERY private map binding and
split output. Never splice candidate kernel bytes into baseline boot artifacts.
Normal worktree build/ and boot images are untouched; each invocation starts a
new directory, so feature flags cannot accidentally reuse old object files.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from default_service_layout import build_report

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT/'build/services/boot'
    out.mkdir(parents=True, exist_ok=True)
    # No stale success pointer if a fresh build fails.
    (out/'latest.json').unlink(missing_ok=True)
    work = Path(tempfile.mkdtemp(prefix='candidate-', dir=out))
    source = work/'source'
    source.mkdir()
    for name in ('src','cfg','mk','tools','user','include','assets','bench'):
        shutil.copytree(ROOT/name, source/name,
            ignore=shutil.ignore_patterns('__pycache__','artifacts','results'))
    shutil.copy2(ROOT/'Makefile', source/'Makefile')
    inputs = {str(path.relative_to(source)):hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(source.rglob('*')) if path.is_file()}
    (work/'inputs.json').write_text(json.dumps(inputs, indent=2)+'\n')
    with (work/'build.log').open('w') as log:
        result = subprocess.run(['make','-j8','boot','placement-check','graphics-apps-check','service-layout-check'],
                                cwd=source, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print((work/'build.log').read_text()[-14000:])
        raise RuntimeError(f'candidate build failed; log: {work / "build.log"}')
    result = build_report(source)
    current = build_report(ROOT)
    for suffix in result['disks']:
        if result['disks'][suffix]['sha256'] != current['disks'][suffix]['sha256']:
            raise ValueError('clean/incremental image mismatch: '+suffix)
    result['input_manifest_sha256'] = hashlib.sha256((work/'inputs.json').read_bytes()).hexdigest()
    result['clean_matches_worktree'] = True
    (work/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    # Convenient test copies, never the ordinary build/boot production media.
    for suffix, info in result['disks'].items():
        shutil.copyfile(info['path'], out/('udeks.'+suffix))
    (out/'latest.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a coherent disk-time candidate from fresh, isolated source copies.

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

from build_time_overlay import overlay_config, qualify
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from service_image import validate

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
    for name in ('8502-bootstrap.cfg', '8502-panic-probe.cfg'):
        cfg = source/'cfg'/name
        # Same single-pass split outputs, now rooted inside the fresh copy.
        cfg.write_text(overlay_config(cfg.read_text(), Path('.')))
    (source/'.udeks-service-candidate').write_text('isolated DISK_TIME=1 build\n')
    with (work/'build.log').open('w') as log:
        result = subprocess.run(['make','-j8','DISK_TIME=1','boot','placement-check','graphics-apps-check'],
                                cwd=source, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print((work/'build.log').read_text()[-14000:])
        raise RuntimeError(f'candidate build failed; log: {work / "build.log"}')
    result = dict(source=str(source), input_manifest_sha256=hashlib.sha256((work/'inputs.json').read_bytes()).hexdigest(),
                  scope='fresh candidate boot images; emulator qualification separate', variants={}, disks={})
    for variant, suffix in (('normal',''),('panic','-panic-probe')):
        base = ROOT/f'build/8502/udeks-8502{suffix}.map'
        candidate = source/f'build/8502/udeks-8502{suffix}.map'
        binary = source/f'build/8502/udeks-8502{suffix}.bin'
        result['variants'][variant] = qualify(map_segments(base.read_text()),map_segments(candidate.read_text()),
            map_exports(candidate.read_text()),binary.read_bytes())
    result['module'] = validate((source/'build/services/time/TIME.SVC').read_bytes())
    for suffix in ('d64','d71','d81'):
        disk = source/f'build/boot/udeks.{suffix}'
        result['disks'][suffix] = dict(path=str(disk), sha256=hashlib.sha256(disk.read_bytes()).hexdigest())
    (work/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    # Convenient test copies, never the ordinary build/boot production media.
    for suffix, info in result['disks'].items():
        shutil.copyfile(info['path'], out/('udeks.'+suffix))
    (out/'latest.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

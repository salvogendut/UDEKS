#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Upgrade a real resident-time build without cleaning or touching user builds."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from default_service_layout import build_report

ROOT = Path(__file__).resolve().parents[1]
BASE = '9eda8ba06a2a5965c9d5ad14943838d10c2e30cf'
INPUTS = ('Makefile','src','cfg','mk','tools','user','include','assets','bench')
SENSITIVE = ('build/8502/service_registry.o', 'build/8502/syscall_gate.o',
             'build/storage/router.o')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def overlay_changed(root, target):
    """Keep unchanged sources and every generated output at their old mtime."""
    changed = []
    for name in INPUTS:
        paths = [root/name] if (root/name).is_file() else sorted((root/name).rglob('*'))
        for path in paths:
            relative = path.relative_to(root)
            if not path.is_file() or any(p in ('__pycache__','artifacts','results') for p in relative.parts):
                continue
            dest = target/relative
            if dest.exists() and dest.read_bytes() == path.read_bytes():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            # copy, not copy2: changed inputs get a fresh timestamp.
            shutil.copy(path, dest)
            changed.append(str(relative))
    (target/'user/etc/rc-services').unlink(missing_ok=True)
    return changed


def main():
    out = ROOT/'build/services/migration'
    out.mkdir(parents=True, exist_ok=True)
    (out/'latest.json').unlink(missing_ok=True)
    work = Path(tempfile.mkdtemp(prefix='upgrade-', dir=out))
    source = work/'source'
    source.mkdir()
    archive = subprocess.check_output(['git','archive',BASE,*INPUTS],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        members = [m for m in tar.getmembers()
                   if not any(p in ('artifacts','results') for p in Path(m.name).parts)]
        tar.extractall(source,members=members,filter='data')

    def build(label, targets):
        with (work/(label+'.log')).open('w') as log:
            result = subprocess.run(['make','-j8',*targets],cwd=source,
                                    stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError('migration failed; see '+str(work/(label+'.log')))

    build('resident',['boot'])
    old_map = source/'build/8502/udeks-8502.map'
    if '\ntime.o:' not in old_map.read_text() or 'SERVICEBOOT' in old_map.read_text():
        raise ValueError('baseline is not the old resident-time layout')
    shutil.copyfile(old_map,work/'resident.map')
    before = {p:digest(source/p) for p in SENSITIVE}
    changed = overlay_changed(ROOT,source)
    build('upgrade',['boot','placement-check','graphics-apps-check','service-layout-check'])
    after = {p:digest(source/p) for p in SENSITIVE}
    if any(before[p]==after[p] for p in SENSITIVE):
        raise ValueError('flag-sensitive object was not migrated')
    report = build_report(source)
    current = build_report(ROOT)
    if any(report['disks'][f]['sha256'] != current['disks'][f]['sha256'] for f in current['disks']):
        raise ValueError('migrated images differ from current normal build')
    def output_times():
        return {str(p.relative_to(source)):p.stat().st_mtime_ns
                for p in (source/'build').rglob('*') if p.is_file()}
    unchanged = output_times()
    build('noop',['boot'])
    if unchanged != output_times():
        raise ValueError('second incremental build was not a no-op')
    report.update(base=BASE,changed_inputs=changed,objects_before=before,
                  objects_after=after,no_clean=True,upgrade_matches_worktree=True,noop=True)
    shutil.copyfile(old_map,work/'upgraded.map')
    (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'latest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()

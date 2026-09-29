#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Preserve the completion checkpoint's shadow/install/layout gate separately."""
import hashlib
import json
import shutil
from pathlib import Path
import shadow_boot_probe as sp
from window_completion_probe import ROOT,WORK,NAME,digest

def qualify(name=NAME, work=WORK, padding=358, raw_work=None):
    frozen=ROOT / 'bench/artifacts' / name
    # Keep the original checkpoint defaults reproducible; later checkpoints
    # must select their own frozen disk, work directory and measured budget.
    report=json.loads((frozen / 'build-report.json').read_text())
    if digest(ROOT / 'build/boot/udeks.d71')!=report['disk_sha256']['d71']:
        raise ValueError('not the completion disk')
    if (work / 'D71.sha256').read_text().split()[0]!=report['disk_sha256']['d71']:
        raise ValueError('shadow probe ran a different disk')
    if digest(ROOT / 'build/8502/udeks-8502.map')!=report['inputs_sha256']['build/8502/udeks-8502.map']:
        raise ValueError('map drift')
    window=(work / 'shadow-boot.bin').read_bytes();pre=(work / 'shadow-preimage.bin').read_bytes()
    if len(window)!=0xcf00-0xa1e0 or len(pre)!=len(window) or any(window[:8000]):
        raise ValueError('shadow clear/window failed')
    tail=window[8000:];old=pre[8000:]
    image=(ROOT / 'build/8502/udeks-scheduler-overlay-tail.bin').read_bytes()
    start,bss,end=sp.scheduler_tail_bounds(ROOT / 'build/8502/udeks-scheduler-overlay.map')
    installed=sp.scheduler_installed_tail(ROOT / 'build/boot/scheduler-overlay.prg')
    context=sp.context_binding_start(ROOT / 'build/8502/task-context-binding.map')
    runtime=end-start+1
    if tail[:len(image)]!=image or tail[runtime:len(installed)]!=installed[runtime:]:
        raise ValueError('scheduler code/gap/handler mismatch')
    if tail[len(installed):context-start]!=old[len(installed):context-start]:
        raise ValueError('tail preimage changed')
    raw=raw_work if raw_work is not None else work / 'shadow-probe'
    page=(raw / 'scheduler-page.bin').read_bytes()
    expected=bytearray((ROOT / 'build/8502/udeks-scheduler-overlay-page.bin').read_bytes())
    expected[-6:]=(ROOT / 'build/8502/task-context-vectors.bin').read_bytes()
    if page!=b'\x00\x1c'+expected:raise ValueError('scheduler page mismatch')
    gate=(raw / 'task-gate.bin').read_bytes()[2:]
    expected=(ROOT / 'build/8502/task-switch-tail.bin').read_bytes()
    if gate[:6]!=expected[:6] or gate[10:179]!=expected[10:179]:raise ValueError('task gate mismatch')
    shadow=(work / 'shadow-drawn.bin').read_bytes();bitmap=(work / 'vic-bitmap.bin').read_bytes()
    if len(shadow)!=8000 or shadow!=bitmap:raise ValueError('bitmap mismatch')
    placement=json.loads((work / 'placement/report.json').read_text())
    if placement['candidate']['qualified_reserve']!=padding or placement['post_shadow']['unowned_bytes']!=0:
        raise ValueError('placement budget changed')
    if placement['inputs_sha256']['build/8502/udeks-8502.map']!=digest(ROOT / 'build/8502/udeks-8502.map'):
        raise ValueError('placement map drift')
    directory=ROOT / 'bench/results' / (name+'-layout')
    if directory.exists():raise ValueError('refusing to overwrite evidence')
    directory.mkdir(parents=True)
    paths=[work / n for n in ('shadow-boot.bin','shadow-preimage.bin','shadow-drawn.bin','vic-bitmap.bin','D71.sha256')]
    paths += [raw / n for n in ('scheduler-page.bin','task-gate.bin','lifecycle-status.bin')]
    paths += [work / 'placement' / n for n in ('raster.lst','transport.lst',
        'cache.segments.txt','rows.segments.txt','transfer.segments.txt')]
    for path in paths:shutil.copy2(path,directory / path.name)
    shutil.copy2(work / 'placement/report.json',directory / 'placement.json')
    inputs=('build/8502/udeks-scheduler-overlay-tail.bin','build/8502/udeks-scheduler-overlay-page.bin',
        'build/8502/task-context-vectors.bin','build/8502/task-switch-tail.bin',
        'build/8502/udeks-scheduler-overlay.map','build/8502/task-context-binding.map',
        'build/boot/scheduler-overlay.prg','tools/shadow_boot_probe.py',
        'tools/window_completion_layout_qualify.py')
    for n in inputs:
        path=directory / n;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT / n,path)
    facts={'disk_sha256':report['disk_sha256']['d71'],'shadow_clear_bytes':8000,
        'tail_preimage_bytes':context-start-len(installed),'remaining_padding':padding,
        'bitmap_sha256':hashlib.sha256(bitmap).hexdigest(),'owned_post_shadow_bytes':3552,
        'qualification':'same frozen disk; clear/install/bitmap/layout only'}
    (directory / 'report.json').write_text(json.dumps(facts,indent=2)+'\n')
    paths=sorted(p for p in directory.rglob('*') if p.is_file())
    (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))
    print(json.dumps(facts,indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',default=NAME)
    parser.add_argument('--work',type=Path,default=WORK)
    parser.add_argument('--remaining-padding',type=int,default=358)
    parser.add_argument('--raw-work',type=Path)
    args=parser.parse_args()
    qualify(args.checkpoint,args.work,args.remaining_padding,args.raw_work)

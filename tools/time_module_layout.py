#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure the module and startup-only reclaim WITHOUT installing an overlay.

This is an accounting gate, not proof that a future loader fits. Normal and
panic code remain unchanged; SERVICEBOOT is emitted only in this candidate.
"""
import json
from pathlib import Path
import re
import subprocess
from build_scheduler_overlay import map_segments
from service_image import TIME_BASE, TIME_LIMIT, validate

ROOT=Path(__file__).resolve().parents[1]


def segments(path):
    result=subprocess.run(['od65','--dump-segments',str(path)],check=True,
                          text=True,capture_output=True).stdout
    return {name:int(size) for name,size in re.findall(r'Name:\s*"([^"]+)".*?Size:\s*(\d+)',result,re.S)}


def main():
    if 'SERVICEBOOT:' in (ROOT/'cfg/8502-bootstrap.cfg').read_text():
        from default_service_layout import main as check_current_layout
        check_current_layout()
        return
    out=ROOT/'build/services/time'
    (out/'placement.json').unlink(missing_ok=True)
    def run(*cmd): subprocess.run(cmd,cwd=ROOT,check=True)
    run('cl65','-t','none','--cpu','6502','--standard','c99','-Oirs','-I','include',
        '-D','UDEKS_SERVICE_BOOT_SPLIT','-c','-o',str(out/'registry-split.o'),
        'src/kernel/service_registry.c')
    original=segments(ROOT/'build/8502/service_registry.o')
    split=segments(out/'registry-split.o')
    if sum(original.values())!=sum(split.values()) or original['BSS']!=split['BSS']:
        raise ValueError('startup split changed total object size or state')
    maps=[map_segments((ROOT/f'build/8502/udeks-8502{suffix}.map').read_text())
          for suffix in ('','-panic-probe')]
    if maps[0]!=maps[1]: raise ValueError('normal/panic segment layouts differ')
    baseline=maps[0]['BSS'][1]+1
    module=validate((out/'TIME.SVC').read_bytes())
    time=segments(ROOT/'build/8502/time.o')['CODE']
    setter=segments(out/'module.o')['CODE']
    # The independent module's CODE object contains exactly the extracted
    # setter/TI include; its 48-byte header lives in a separate segment.
    if not time or not setter or not split['SERVICEBOOT']:
        raise ValueError('missing measured reclaim object')
    minimum=baseline-time-setter-split['SERVICEBOOT']
    manager=segments(out/'time-slot.o')
    manager_bytes=sum(manager.values())
    run('cl65','-t','none','--cpu','6502','--standard','c99','-Oirs','-I','include',
        '-c','-o',str(out/'resident.o'),'src/services/time/resident.c')
    compatibility=segments(out/'resident.o')['CODE']
    budget=TIME_BASE-minimum
    report=dict(scope='pre-integration accounting, NOT a resident link or safe-to-load image',
                baseline_bss_end=baseline-1, time_code=time, setter_and_ti=setter,
                registry_boot_only=split['SERVICEBOOT'], registry_live=split['CODE'],
                registry_bss=split['BSS'], module_allocation=module['allocation'],
                candidate_base=TIME_BASE, candidate_limit=TIME_LIMIT,
                reservation=TIME_LIMIT-TIME_BASE,
                baseline_overlap=baseline-TIME_BASE,
                predicted_end_before_manager=minimum,
                max_new_resident_bytes_before_slot=budget,
                manager_segments=manager, manager_bytes=manager_bytes,
                retained_clock_read_bytes=compatibility,
                manager_shortfall_before_request_glue=max(0,manager_bytes+compatibility-budget),
                manager_fits_before_request_glue=manager_bytes+compatibility<=budget,
                conditions=['remove old time code and setter',
                            'place SERVICEBOOT inside the future module slot',
                            'permanent one-shot startup guard before overwrite',
                            'link actual dispatch/loader/lifecycle state below candidate base'])
    if split['SERVICEBOOT']>TIME_LIMIT-TIME_BASE or minimum>TIME_BASE:
        raise ValueError('proposed boot overlay cannot accommodate measured code')
    (out/'placement.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()

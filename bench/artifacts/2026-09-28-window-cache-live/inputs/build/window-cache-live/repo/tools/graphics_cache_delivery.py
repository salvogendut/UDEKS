#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build/qualify isolated cache-core delivery disks; never change normal boot outputs."""
import argparse
import hashlib
import importlib
import json
import os
import shutil
import shlex
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/graphics-cache-delivery'
CORE = 0x4200
HEADER = 0x43F0
SCHEDULER = 0x5000
CORE_BYTES = 512
NAME = '2026-09-28-window-cache-delivery'
PROOF = ROOT / 'bench/artifacts/2026-09-28-window-cache-overlay'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def envelope(scheduler, core):
    if not core or len(core)>HEADER-CORE:
        raise ValueError('core is empty or reaches private identity header')
    if len(scheduler)<22 or scheduler[:8]!=b'\x00\x50USOV\x00\x03':
        raise ValueError('canonical scheduler must be $5000 USOV 0.3')
    h=scheduler[2:22]
    page=int.from_bytes(h[8:10],'little');tail=int.from_bytes(h[12:14],'little')
    if h[6:8]!=b'\x00\x1c' or page!=1024 or h[10:12]!=b'\x20\xc1':
        raise ValueError('scheduler page/tail placement changed')
    bss=int.from_bytes(h[14:16],'little');bss_bytes=int.from_bytes(h[16:18],'little')
    if tail<256 or 0xc120+tail>0xcdbd or not 0<bss_bytes<=255 or not 0xc120<=bss<0xc900 or bss+bss_bytes>0xc900:
        raise ValueError('scheduler tail/BSS reservation changed')
    if len(scheduler)!=22+page+tail+234+192:
        raise ValueError('canonical scheduler/activation length changed')
    if int.from_bytes(h[18:20],'little')!=(sum(scheduler[22:22+page+tail])&65535):
        raise ValueError('scheduler checksum mismatch')
    if SCHEDULER+len(scheduler)-2>0x8000:
        raise ValueError('secondary payload exceeds boot source reservation')
    identity=(b'VCC1\x00\x01'+CORE.to_bytes(2,'little')+
              len(core).to_bytes(2,'little')+(sum(core)&65535).to_bytes(2,'little')+bytes(4))
    prefix=core.ljust(HEADER-CORE,b'\x00')+identity
    prefix=prefix.ljust(SCHEDULER-CORE,b'\x00')
    return CORE.to_bytes(2,'little')+prefix+scheduler[2:]


def validate_slot(slot, core):
    if len(slot)!=CORE_BYTES:
        raise ValueError('cache code lease capture is not 512 bytes')
    expected=envelope_fixture(core)[:CORE_BYTES]
    if slot!=expected:
        raise ValueError('delivered core/identity/padding changed')
    return {'bytes':len(core),'slot_sha256':hashlib.sha256(slot).hexdigest(),
            'core_sha256':hashlib.sha256(slot[:len(core)]).hexdigest()}


def envelope_fixture(core):
    if not core or len(core)>HEADER-CORE:raise ValueError('invalid core size')
    header=(b'VCC1\x00\x01'+CORE.to_bytes(2,'little')+len(core).to_bytes(2,'little')+
            (sum(core)&65535).to_bytes(2,'little')+bytes(4))
    return core.ljust(HEADER-CORE,b'\x00')+header


def disk_command(text):
    logical=text.replace('\\\n',' ')
    matches=[shlex.split(line) for line in logical.splitlines()
             if line.startswith('python3 tools/build_d71.py ')]
    if len(matches)!=1:raise ValueError('ambiguous normal disk build recipe')
    return matches[0]


def build():
    WORK.mkdir(parents=True,exist_ok=True)
    core=(PROOF / 'build/core.bin').read_bytes()
    for line in (PROOF / 'SHA256SUMS').read_text().splitlines():
        sha,name=line.split('  ',1)
        if digest(PROOF / name)!=sha:raise ValueError('qualified core proof changed')
    canonical=ROOT / 'build/boot/scheduler-overlay.prg'
    payload=envelope(canonical.read_bytes(),core)
    secondary=WORK / 'secondary.prg';secondary.write_bytes(payload)
    (WORK / 'core.bin').write_bytes(core)
    source=(ROOT / 'src/boot/stage1.s').read_text()
    for old,new in (('ldx #<SCHEDULER_OVERLAY_LOAD','ldx #<$4200'),
                    ('ldy #>SCHEDULER_OVERLAY_LOAD','ldy #>$4200')):
        if source.count(old)!=1:raise ValueError('secondary load argument changed')
        source=source.replace(old,new)
    asm=WORK / 'stage1.s';asm.write_text(source)
    subprocess.run(['ca65','--cpu','6502','-I',str(ROOT / 'build/8502'),
        '-o',str(WORK / 'stage1.o'),str(asm)],check=True)
    stage=WORK / 'stage1.bin'
    subprocess.run(['ld65','-C',str(ROOT / 'cfg/8502-stage1.cfg'),
        '-m',str(WORK / 'stage1.map'),'-o',str(stage),str(WORK / 'stage1.o')],check=True)
    original=(ROOT / 'build/boot/stage1.bin').read_bytes();changed=stage.read_bytes()
    diff=[i for i,(a,b) in enumerate(zip(original,changed)) if a!=b]
    if len(original)!=len(changed) or len(diff)!=1 or diff[0]<0x3bb or (
            original[diff[0]],changed[diff[0]])!=(0x50,0x42):
        raise ValueError('experimental stage1 changes more than relocation high byte')
    command=disk_command(subprocess.check_output(['make','-Bn','build/boot/udeks.d71'],cwd=ROOT,text=True))
    command[command.index('--stage1')+1]=str(stage)
    command[command.index('--scheduler-overlay')+1]=str(secondary)
    command[command.index('--d64-output')+1]=str(WORK / 'delivery.d64')
    command[-1]=str(WORK / 'delivery.d71')
    subprocess.run(command,cwd=ROOT,check=True)
    paths=[ROOT / 'src/boot/stage1.s',ROOT / 'build/boot/stage1.bin',
           ROOT / 'build/boot/stage1-gateway.bin',
           ROOT / 'build/8502/scheduler-overlay-delivery.inc',
           ROOT / 'cfg/8502-stage1.cfg',canonical,
           ROOT / 'tools/build_d71.py',ROOT / 'tools/shadow_boot_probe.py',
           ROOT / 'tools/capability_relocation_probe.py',ROOT / 'tools/vice_capture.py',
           ROOT / 'tools/1986_input_smoke_build.py',ROOT / 'tools/1986_input_smoke.c',
           ROOT / 'tools/graphics_raster_bench_run.py',ROOT / 'tools/graphics_span_bench.py',
           ROOT / 'tools/placement_audit.py',
           ROOT / 'tools/bench_decode.py',Path(__file__),ROOT / 'Makefile']
    for argument in command:
        p=Path(argument)
        if p.is_file() and p.resolve().is_relative_to(ROOT) and not p.resolve().is_relative_to(WORK):
            paths.append(p.resolve())
    report={'qualification':'experimental cold-boot delivery only; no enabled pixel cache or module execution',
        'canonical_load':SCHEDULER,'secondary_load':CORE,
        'end':CORE+len(payload)-2,'prefix_bytes':SCHEDULER-CORE,
        'stage1_changed_offset':diff[0],'core_sha256':digest(WORK / 'core.bin'),
        'canonical_sha256':digest(canonical),'disk_recipe':command,
        'disk_sha256':{name:digest(WORK / name) for name in ('delivery.d71','delivery.d64')},
        'normal_disks_before':{name:digest(ROOT / 'build/boot' / name) for name in ('udeks.d71','udeks.d64')},
        'inputs_sha256':{str(p.relative_to(ROOT)):digest(p) for p in sorted(set(paths))}}
    (WORK / 'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('inputs_sha256','disk_recipe')},indent=2))


def verify(report):
    for name,sha in report['inputs_sha256'].items():
        if digest(ROOT / name)!=sha:raise ValueError('input drift: '+name)
    for name,sha in report['disk_sha256'].items():
        if digest(WORK / name)!=sha:raise ValueError('disk drift: '+name)
    for name,sha in report['normal_disks_before'].items():
        if digest(ROOT / 'build/boot' / name)!=sha:raise ValueError('normal boot output changed: '+name)
    if digest(WORK / 'core.bin')!=report['core_sha256']:raise ValueError('core drift')


def probe_vice():
    import shadow_boot_probe as sp
    from capability_relocation_probe import inject_until_state
    from vice_capture import choose_port,monitor_command,parse_monitor_byte
    report=json.loads((WORK / 'build-report.json').read_text());verify(report)
    core=(WORK / 'core.bin').read_bytes()
    symbols=sp.symbol_addresses(ROOT / 'build/8502/udeks-8502.map')
    (WORK / 'vice-provenance.txt').write_text(subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True))
    result={}
    for fmt in ('d71','d64'):
        port=choose_port();process,master=sp.launch_vice(WORK / f'delivery.{fmt}',port,'net.sf.VICE')
        snapshots={}
        try:
            time.sleep(6)
            deadline=time.monotonic()+150
            sp.wait_for_byte(port,sp.ROOT_TERMINAL_STATUS_READY_ADDRESS,2,deadline)
            sp.wait_for_byte(port,0xf116,1,deadline)
            def capture(label):
                path=WORK / f'vice-{fmt}-{label}-core.bin'
                slot=sp.capture_blocks(port,[(path,CORE,CORE+CORE_BYTES-1,'worker')])[0]
                snapshots[label]=validate_slot(slot,core)
            capture('boot')
            for command,address,state,label in (
                ('xinit',0xf1b5,3,'xinit'),('xclock &',0xf225,3,'clock'),
                ('xwave &',0xf265,3,'wave')):
                inject_until_state(port,symbols,command,address,state,deadline)
                capture(label)
            sp.wait_for_byte(port,0xf27a,21,deadline)
            capture('complete')
            for command in ('cowsay delivery','ls','cd bin','pwd','echo module-intact'):
                before=parse_monitor_byte(monitor_command(port,'m f3d8 f3d8'),0xf3d8)
                sp.inject_line(port,symbols,command)
                sp.wait_for_byte(port,0xf3d8,(before+1)&255,deadline)
            capture('utilities')
            sp.inject_line(port,symbols,'xinit -q')
            sp.wait_for_byte(port,0xf1b5,2,deadline)
            capture('shutdown')
            inject_until_state(port,symbols,'xinit',0xf1b5,3,deadline)
            capture('restart')
            result[fmt]=snapshots
            print(f'VICE {fmt}: core survives '+', '.join(snapshots),flush=True)
        finally:
            sp.terminate(process,port);os.close(master)
    verify(report)
    (WORK / 'vice-results.json').write_text(json.dumps(result,indent=2)+'\n')


def probe_1986():
    from bench_decode import extract_memory
    from graphics_raster_bench_run import emulator_provenance
    report=json.loads((WORK / 'build-report.json').read_text());verify(report)
    emulator=ROOT.parent / '1986'
    sources=importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
    before=emulator_provenance(emulator,sources)
    result={}
    for fmt in ('d71','d64'):
        snapshot=WORK / f'1986-{fmt}.vsf';log=WORK / f'1986-{fmt}.log'
        subprocess.run(['python3','tools/1986_input_smoke_build.py','--roms',str(emulator / 'roms'),
            '--disk',str(WORK / f'delivery.{fmt}'),'--drag-stress','32','--drag-clock',
            '--output',str(WORK / '1986-delivery-runner'),'--snapshot',str(snapshot),'--log',str(log)],cwd=ROOT,check=True)
        slot=extract_memory(snapshot.read_bytes(),0x10000+CORE,CORE_BYTES)
        (WORK / f'1986-{fmt}-core.bin').write_bytes(slot)
        result[fmt]=validate_slot(slot,(WORK / 'core.bin').read_bytes())
    if emulator_provenance(emulator,sources)!=before:raise ValueError('emulator drift')
    verify(report)
    (WORK / '1986-provenance.json').write_text(json.dumps(before,indent=2)+'\n')
    (WORK / '1986-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


def measure_policy():
    from graphics_span_bench import object_sizes
    from placement_audit import parse_map
    WORK.mkdir(parents=True,exist_ok=True)
    source=ROOT / 'src/services/window/move_cache_state.c'
    header=ROOT / 'include/udeks/window_cache_state.h'
    config=ROOT / 'bench/window-cache-overlay/policy-link.cfg'
    qualified=PROOF / 'bench/window-cache-overlay'
    obj=WORK / 'move-cache-state.o';binary=WORK / 'policy-module.bin';mapfile=WORK / 'policy-module.map'
    subprocess.run(['cl65','-t','none','--cpu','6502','-Oirs','--standard','c99',
        '-I',str(ROOT / 'include'),'-c','-o',str(obj),str(source)],check=True)
    # Measure actual cc65 record allocation, not host sizeof or a packed-wire
    # assumption. The two layout probes are NOT included in the module link.
    records={}
    for name in ('lease','row'):
        probe=WORK / f'size-{name}.c'
        probe.write_text('#include "udeks/window_cache_state.h"\nstruct udeks_cache_'+name+' record;\n')
        subprocess.run(['cl65','-t','none','-I',str(ROOT / 'include'),'-c',
            '-o',str(probe.with_suffix('.o')),str(probe)],check=True)
        records[name]=object_sizes(probe.with_suffix('.o'))['BSS']
    if records!={'lease':13,'row':9}:raise ValueError('cc65 cache record layout changed')
    subprocess.run(['ca65','-I',str(qualified),'-o',str(WORK / 'policy-core.o'),
        str(qualified / 'core.s')],check=True)
    subprocess.run(['cl65','-t','none','--cpu','6502','-C',str(config),
        '-m',str(mapfile),'-o',str(binary),str(WORK / 'policy-core.o'),str(obj)],check=True)
    objects,segments=parse_map(mapfile.read_text())
    by_name={name:(start,end) for name,start,end in segments}
    size=object_sizes(obj)
    if size['BSS'] or size['ZEROPAGE'] or by_name['ZEROPAGE']!=(6,31):
        raise ValueError('policy acquired private/global state or changed the UAPP zero-page layout')
    length=binary.stat().st_size
    linked_core=(PROOF / 'build/core.bin').read_bytes()
    if binary.read_bytes()[:len(linked_core)]!=linked_core:
        raise ValueError('measured policy link does not preserve the qualified row core')
    report={'qualification':'host-tested C policy and unexecuted bank-1 link; no private-stack/dispatcher qualification',
        'cc65':subprocess.check_output(['cc65','--version'],stderr=subprocess.STDOUT,text=True).strip(),
        'policy_object':size,'linked_bytes':length,'core_bytes':len(linked_core),
        'cc65_record_bytes':records,
        'helper_bytes':length-size['CODE']-len(linked_core),
        'segments':{name:[start,end] for name,start,end in segments},
        'helpers':sorted(name for name in objects if 'none.lib(' in name),
        'binary_sha256':digest(binary),'map_sha256':digest(mapfile),
        'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in (source,header,config)},
        'candidate_private_stack':[0x4d00,0x4def],
        'candidate_identity':[0x4df0,0x4dff],
        'candidate_image':[0x4e00,0x5bff],
        'warning':'candidate is not delivered or executed; current delivery disk still contains only the 213-byte row core'}
    (WORK / 'policy-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


def preserve():
    report=json.loads((WORK / 'build-report.json').read_text());verify(report)
    core=(WORK / 'core.bin').read_bytes()
    vice=json.loads((WORK / 'vice-results.json').read_text())
    native=json.loads((WORK / '1986-results.json').read_text())
    expected_labels={'boot','xinit','clock','wave','complete','utilities','shutdown','restart'}
    if set(vice)!={'d71','d64'} or set(native)!={'d71','d64'}:
        raise ValueError('missing disk format qualification')
    for fmt in ('d71','d64'):
        if set(vice[fmt])!=expected_labels:raise ValueError('incomplete VICE lifetime gate')
        for label in sorted(expected_labels):
            slot=(WORK / f'vice-{fmt}-{label}-core.bin').read_bytes()
            if slot[:2]!=CORE.to_bytes(2,'little') or validate_slot(slot[2:],core)!=vice[fmt][label]:
                raise ValueError('VICE capture drift')
        if validate_slot((WORK / f'1986-{fmt}-core.bin').read_bytes(),core)!=native[fmt]:
            raise ValueError('native capture drift')
        log=(WORK / f'1986-{fmt}.log').read_text()
        if ('PASS: repeated native wave drags and console cancellation' not in log or
                sum(line.startswith('stress ') for line in log.splitlines())!=32):
            raise ValueError('native drag/input gate missing')
    policy=json.loads((WORK / 'policy-report.json').read_text())
    for name,sha in policy['source_sha256'].items():
        if digest(ROOT / name)!=sha:raise ValueError('policy source drift')
    if digest(WORK / 'policy-module.bin')!=policy['binary_sha256'] or digest(WORK / 'policy-module.map')!=policy['map_sha256']:
        raise ValueError('policy link drift')
    artifacts=ROOT / 'bench/artifacts' / NAME;results=ROOT / 'bench/results' / NAME
    if artifacts.exists() or results.exists():raise ValueError('refusing to overwrite evidence')
    artifacts.mkdir(parents=True);results.mkdir(parents=True)
    for name in sorted(set(report['inputs_sha256'])|set(policy['source_sha256'])):
        target=artifacts / name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT / name,target)
    build_dir=artifacts / 'build';build_dir.mkdir(exist_ok=True)
    for name in ('build-report.json','policy-report.json','core.bin','stage1.s','stage1.bin','stage1.map',
                 'secondary.prg','delivery.d71','delivery.d64','policy-module.bin','policy-module.map'):
        shutil.copy2(WORK / name,build_dir / name)
    for pattern in ('vice-*.bin','1986-*-core.bin','1986-*.log','*-results.json','*-provenance.*'):
        for path in WORK.glob(pattern):shutil.copy2(path,results / path.name)
    for directory in (artifacts,results):
        paths=sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))
    print('preserved experimental delivery and unexecuted policy link; no ROMs or full snapshots')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('build','vice','1986','measure-policy','preserve'))
    args=parser.parse_args()
    if args.action=='build':build()
    elif args.action=='vice':probe_vice()
    elif args.action=='1986':probe_1986()
    elif args.action=='measure-policy':measure_policy()
    else:preserve()


if __name__=='__main__':main()

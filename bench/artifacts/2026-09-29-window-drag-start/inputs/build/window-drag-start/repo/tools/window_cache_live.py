#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build an isolated, bootable cached-compositor disk; keep normal outputs intact."""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from graphics_raster_link_audit import segments
from gen_capability_imports import map_exports
from window_cache_controller_delivery import envelope, relocated_constants
from window_cache_manager import candidate

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/window-cache-live'
REPO = WORK / 'repo'
PROOF = ROOT / 'bench/artifacts/2026-09-28-window-cache-compact'
MODULE_REL = 'build/bench/window-cache-compact/module.bin'
LOADER_REL = 'build/bench/window-cache-compact/acceptance/loader.inc'
NAME = '2026-09-28-window-cache-live'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_build():
    report=json.loads((WORK / 'report.json').read_text())
    for key,root in (('inputs_sha256',ROOT),('source_sha256',ROOT),
                     ('normal_outputs_unchanged',ROOT)):
        for name,sha in report[key].items():
            if digest(root / name)!=sha:raise ValueError('build binding drift '+name)
    for fmt,sha in report['disk_sha256'].items():
        if digest(WORK / f'udeks-cache.{fmt}')!=sha:raise ValueError('test disk changed '+fmt)
    return report


def validate_live_slot(slot, module, width, height):
    from window_cache_controller_delivery import validate_slot
    # The executed row core has two self-modifying address operands and four
    # scratch bytes, unlike the earlier *uninvoked* delivery proof. Check
    # operands against the completed final row, and all other bytes exactly.
    if len(slot)!=4128 or not 0<width<=320 or not 0<height<=200:
        raise ValueError('invalid live slot/geometry')
    if module[0x4c:0x4f]!=b'\x9d\xff\xff' or module[0x73:0x76]!=b'\xbd\xff\xff':
        raise ValueError('qualified row operand layout changed')
    address=0x5350+(height-1)*((width+7)//8)
    for offset in (0x4d,0x74):
        if int.from_bytes(slot[offset:offset+2],'little')!=address:
            raise ValueError('last row pointer outside completed image')
    normalized=bytearray(slot)
    for offset in (0x4d,0x4e,0x74,0x75,0xd1,0xd2,0xd3,0xd4):
        normalized[offset]=module[offset]
    return validate_slot(bytes(normalized),module)


def copy_inputs():
    REPO.mkdir(parents=True, exist_ok=True)
    for name in ('src','include','cfg','user','assets','tools','bench','mk'):
        shutil.copytree(ROOT / name, REPO / name, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('artifacts','results','__pycache__'))
    shutil.copy2(ROOT / 'Makefile', REPO / 'Makefile')


def transport_source():
    binding=(ROOT / 'bench/window-cache-acceptance/binding.s').read_text()
    binding=binding.replace('        .import _cache_raw_call\n','').replace(
        'build/bench/window-cache-acceptance/validator.bin','src/8502/cache-validator.bin')
    raw=(ROOT / 'bench/window-cache-compact/raw.s').read_text()
    raw=raw.replace('        .include "layout.inc"\n','').replace(
        '        .import _udeks_nmi_drain, _cache_copy_fault_probe\n','')
    for name in ('install','copy','loader_image','loader_end'):
        raw=re.sub(r'\b'+name+r'\b','compact_'+name,raw)
    driver=(PROOF / 'build/driver.s').read_text()
    marker='.segment "CODE"\n.export _cache_copy_fault_probe\n'
    helper=marker+driver.split(marker)[1]
    return binding+'\n'+raw+'\n'+helper+'''
.segment "CODE"
.export _cache_command
_cache_command:
        sta OP
        jmp _private_cache_policy_call
'''


def build(extra_inputs=()):
    from graphics_span_bench import object_sizes
    from placement_audit import parse_map
    baseline={str(p.relative_to(ROOT)):digest(p) for d in ('build/8502','build/boot','build/user')
              for p in (ROOT / d).rglob('*') if p.is_file()}
    for line in (PROOF / 'SHA256SUMS').read_text().splitlines():
        sha,name=line.split('  ',1)
        if digest(PROOF / name)!=sha:raise ValueError('compact proof drift '+name)
    copy_inputs()
    (REPO / 'src/services/window/window_manager.c').write_text(candidate(
        (ROOT / 'src/services/window/window_manager.c').read_text()))
    wave=REPO / 'src/apps/xwave.c'
    wave.write_text(wave.read_text().replace('    STATUS_BYTE(8) = window_handle;\n','').replace(
        '    /* A focused window', '    STATUS_BYTE(8) = handle;\n\n    /* A focused window'))
    source=REPO / 'src/8502'
    (source / 'cache_transport.s').write_text(transport_source())
    for name,path in (('layout.inc',ROOT / 'bench/window-cache-controller/layout.inc'),
        ('acceptance.inc',PROOF / 'build/acceptance.inc'),
        ('loader.inc',PROOF / LOADER_REL),
        ('cache-validator.bin',PROOF / 'build/validator.bin')):
        shutil.copy2(path,source / name)
    make=(REPO / 'Makefile').read_text()
    old='$(BUILD_8502)/window_manager.o \\\n'
    if make.count(old)!=2:raise ValueError('resident manager prerequisites changed')
    make=make.replace(old,'$(BUILD_8502)/window_manager.o $(BUILD_8502)/cache_transport.o \\\n')
    make+='''
$(BUILD_8502)/cache_transport.o: src/8502/cache_transport.s | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -I src/8502 -o $@ $<
'''
    (REPO / 'Makefile').write_text(make)
    # Spend all old padding on the first link; then reclaim the measured
    # shadow displacement as held padding. Never package a shifted shadow.
    original=(ROOT / 'src/8502/vic_graphics.s').read_text()
    spent=original
    for label,count in (('raster_scratch_placement_reserve',49),
        ('raster_primitives_placement_reserve',173),('raster_shared_placement_reserve',280)):
        old=f'{label}:\n        .res {count}, $ea'
        if spent.count(old)!=1:raise ValueError('padding changed '+label)
        spent=spent.replace(old,f'{label}:\n        .res 0, $ea')
    transport=source / 'vic_graphics.s';transport.write_text(spent)
    subprocess.run(['make','-j8','build/8502/udeks-8502.bin','build/8502/udeks-8502-panic-probe.bin'],
                   cwd=REPO,check=True)
    normal=REPO / 'build/8502/udeks-8502.map'
    pad=0xa1e0-segments(normal.read_text())['VICSHADOW']['start']
    if not 0<=pad<=502:raise ValueError('candidate does not fit qualified resident budget')
    transport.write_text(spent.replace('raster_shared_placement_reserve:\n        .res 0, $ea',
                                       f'raster_shared_placement_reserve:\n        .res {pad}, $ea'))
    subprocess.run(['make','-j8','boot'],cwd=REPO,check=True)
    current=segments(normal.read_text())
    helpers={}
    for name in ('udeks-8502','udeks-8502-panic-probe'):
        if segments((REPO / 'build/8502' / (name+'.map')).read_text()) != segments(
                (ROOT / 'build/8502' / (name+'.map')).read_text()):
            raise ValueError('frozen segment drift '+name)
        old_modules=parse_map((ROOT / 'build/8502' / (name+'.map')).read_text())[0]
        new_modules=parse_map((REPO / 'build/8502' / (name+'.map')).read_text())[0]
        old_helpers={n:s for n,s in old_modules.items() if n.startswith('none.lib(')}
        new_helpers={n:s for n,s in new_modules.items() if n.startswith('none.lib(')}
        if old_helpers!=new_helpers:raise ValueError('runtime helper drift '+name)
        helpers[name]=new_helpers
    if object_sizes(REPO / 'build/8502/cache_transport.o')['CODE']!=377:
        raise ValueError('full transport charge changed')
    # Move only TEMPORARY scheduler sources, package the exact qualified module.
    boot=REPO / 'build/boot'; asm=REPO / 'build/8502'
    module=(PROOF / MODULE_REL).read_bytes()
    (boot / 'cache-secondary.prg').write_bytes(envelope((boot / 'scheduler-overlay.prg').read_bytes(),module))
    delivery=REPO / 'build/cache-delivery';delivery.mkdir(exist_ok=True)
    (delivery / 'scheduler-overlay-delivery.inc').write_text(relocated_constants(
        (asm / 'scheduler-overlay-delivery.inc').read_text()))
    def assemble(name,cfg,input_path=None):
        subprocess.run(['ca65','--cpu','6502','-I',str(delivery),'-o',str(delivery / (name+'.o')),
            str(input_path or REPO / 'src/boot' / (name+'.s'))],cwd=REPO,check=True)
        subprocess.run(['ld65','-C',str(REPO / 'cfg' / (cfg+'.cfg')),
            '-o',str(delivery / (name+'.bin')),str(delivery / (name+'.o'))],cwd=REPO,check=True)
    for name in ('scheduler-tail-installer','task-switch-activation'):
        assemble(name,'8502-'+name)
    # Import the isolated generator in a subprocess: its ROOT is the private
    # repository. Never bind a changed kernel to stale production addresses.
    subprocess.run(['python3','tools/gen_boot_console_imports.py','constants',
        str(boot / '8502-boot-console.bin'),str(boot / '8502-boot-delivery.bin'),
        str(boot / '8502-capability.bin'),str(boot / 'capability-installer.bin'),
        str(delivery / 'task-switch-activation.bin'),str(normal),
        str(asm / 'udeks-8502-panic-probe.map'),str(delivery / 'boot-console-delivery.inc')],cwd=REPO,check=True)
    assemble('boot-console-installer','8502-boot-console-installer')
    stage=(REPO / 'src/boot/stage1.s').read_text().replace('ldx #<SCHEDULER_OVERLAY_LOAD','ldx #<$4200').replace(
        'ldy #>SCHEDULER_OVERLAY_LOAD','ldy #>$4200')
    (delivery / 'stage1.s').write_text(stage)
    assemble('stage1','8502-stage1',delivery / 'stage1.s')
    from graphics_cache_delivery import disk_command
    command=disk_command(subprocess.check_output(['make','-Bn','build/boot/udeks.d71'],cwd=REPO,text=True))
    for flag,path in (('--stage1',delivery / 'stage1.bin'),('--scheduler-overlay',boot / 'cache-secondary.prg'),
        ('--scheduler-tail-installer',delivery / 'scheduler-tail-installer.bin'),
        ('--task-switch-activation',delivery / 'task-switch-activation.bin'),
        ('--boot-console-installer',delivery / 'boot-console-installer.bin'),('--d64-output',WORK / 'udeks-cache.d64')):
        command[command.index(flag)+1]=str(path)
    command[-1]=str(WORK / 'udeks-cache.d71')
    subprocess.run(command,cwd=REPO,check=True)
    symbols=map_exports(normal.read_text())
    paths=sorted(p for p in REPO.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    report={'qualification':'isolated bootable cache compositor candidate; emulator gates pending',
        'remaining_padding':pad,'segments':current,'transport_bytes':377,
        'manager_sizes':object_sizes(REPO / 'build/8502/window_manager.o'),
        'cc65':subprocess.check_output(['cc65','--version'],stderr=subprocess.STDOUT,text=True).strip(),
        'symbols':{n:v[0] for n,v in symbols.items() if n.startswith('_cache_')},
        'disk_sha256':{fmt:digest(WORK / f'udeks-cache.{fmt}') for fmt in ('d71','d64')},
        'inputs_sha256':{str(p.relative_to(ROOT)):digest(p) for p in paths},
        'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in (
            Path(__file__),ROOT / 'tools/window_cache_manager.py',
            ROOT / 'bench/window-cache-manager/adapter.inc',
            ROOT / 'bench/window-cache-manager/native.inc',
            ROOT / 'tools/1986_input_smoke.c',ROOT / 'tests/test_window_cache_manager.py',
            ROOT / 'tests/test_window_cache_live.py',PROOF / 'SHA256SUMS',*extra_inputs)},
        'normal_outputs_unchanged':baseline,'helpers':helpers,
        'normal_disks':{fmt:digest(ROOT / 'build/boot' / f'udeks.{fmt}') for fmt in ('d71','d64')}}
    (WORK / 'report.json').write_text(json.dumps(report,indent=2)+'\n')
    verify_build()
    print(json.dumps({k:report[k] for k in ('qualification','remaining_padding',
        'transport_bytes','manager_sizes','disk_sha256','normal_disks')},indent=2))


def probe_native(transform=None):
    from importlib import import_module
    from graphics_raster_bench_run import emulator_provenance
    from window_completion_probe import window_base
    builder=import_module('1986_input_smoke_build')
    report=verify_build()
    emulator=ROOT.parent / '1986';sources=builder.emulator_sources(emulator)
    provenance=emulator_provenance(emulator,sources)
    original=(ROOT / 'tools/1986_input_smoke.c').read_text()
    # 1986 uses positional C128 bindings: the PC '=' key is the C128 '-'.
    # Keep native matrix sampling, but select the actual minus key for -q.
    original=original.replace("key(SDL_SCANCODE_MINUS)","key(SDL_SCANCODE_EQUALS)")
    head,tail=original.split('static void drag_stress(unsigned count) {',1)
    main='int main('+tail.split('int main(',1)[1]
    constants={'CACHE_WINDOWS':window_base((REPO / 'build/8502/udeks-8502.map').read_text()),
        'CACHE_ACCEPT':report['symbols']['_cache_accept_state'],
        'CACHE_PHASE':report['symbols']['_cache_phase'],'CACHE_OWNER':report['symbols']['_cache_owner']}
    code=head+'\n'.join(f'#define {k} 0x{v:04x}u' for k,v in constants.items())+'\n'+(
        ROOT / 'bench/window-cache-manager/native.inc').read_text()+'\n'+main
    if transform is not None:code=transform(code)
    (WORK / 'native.c').write_text(code)
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
    runner=WORK / 'native'
    subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator / 'src'),str(WORK / 'native.c'),
        *map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    environment=os.environ.copy();environment.update(UDEKS_DRAG_STRESS='16',UDEKS_DRAG_CLOCK='1')
    results={}
    for fmt in ('d71','d64'):
        command=[str(runner),str(emulator / 'roms'),str(WORK / f'udeks-cache.{fmt}'),
            builder.slot_address(REPO / 'build/8502/udeks-scheduler-overlay.map'),str(WORK / f'1986-{fmt}.vsf')]
        process=subprocess.run(command,env=environment,text=True,capture_output=True)
        (WORK / f'1986-{fmt}.log').write_text(process.stdout+process.stderr)
        print(process.stdout+process.stderr,flush=True)
        if process.returncode:raise ValueError('native compositor failed '+fmt)
        from bench_decode import extract_memory
        snapshot=(WORK / f'1986-{fmt}.vsf').read_bytes()
        blocks={'shadow':(0xa1e0,8000),'bitmap':(0x16000,8000),
                'image':(0x15350,2224),'window':(constants['CACHE_WINDOWS'],68),
                'slot':(0x14200,4128),'guards':(0x1523a,22),'stack-guard':(0x15340,16),
                'wave':(0xf260,32),'nmi':(0xffd0,48)}
        raw={n:extract_memory(snapshot,a,size) for n,(a,size) in blocks.items()}
        module=(PROOF / MODULE_REL).read_bytes()
        if any(raw['guards']+raw['stack-guard']):raise ValueError('private guards changed')
        window=next(raw['window'][i:i+17] for i in range(0,68,17)
                    if raw['window'][i:i+2]==b'\x01\x02')
        pixels=bitmap_oracle(raw['shadow'],raw['bitmap'],raw['image'],window)
        validate_live_slot(raw['slot'],module,pixels['geometry'][2],pixels['geometry'][3])
        for name,value in raw.items():(WORK / f'1986-{fmt}-{name}.bin').write_bytes(value)
        results[fmt]={**pixels,'log_sha256':digest(WORK / f'1986-{fmt}.log')}
    if emulator_provenance(emulator,sources)!=provenance:raise ValueError('emulator changed during run')
    verify_build()
    (WORK / '1986-run.json').write_text(json.dumps({'provenance':provenance,'results':results,
        'report_sha256':digest(WORK / 'report.json'),
        'raw_sha256':{p.name:digest(p) for p in sorted(WORK.glob('1986-*.bin'))},
        'runner_sha256':digest(WORK / 'native'),'source_sha256':digest(WORK / 'native.c')},indent=2)+'\n')


def bitmap_oracle(shadow, bitmap, image, window):
    if (len(shadow),len(bitmap),len(image),len(window))!=(8000,8000,2224,17):
        raise ValueError('pixel oracle record length changed')
    x=int.from_bytes(window[4:6],'little');y=window[6]
    width=int.from_bytes(window[7:9],'little');height=window[9]
    if window[:3]!=b'\x01\x02\x01' or (width,height)!=(168,104) or x>152 or y>96:
        raise ValueError('completed wave geometry/owner changed')
    for yy in range(height):
        for xx in range(width):
            offset=((y+yy)&248)*40+((y+yy)&7)+((x+xx)&~7)
            bit=7-((x+xx)&7)
            expected=(image[yy*21+xx//8]>>(7-(xx&7)))&1
            if (shadow[offset]>>bit)&1 != expected or (bitmap[offset]>>bit)&1 != expected:
                raise ValueError(f'cached pixel mismatch at {xx},{yy}')
    if shadow!=bitmap:raise ValueError('full VIC bitmap differs from shadow')
    return {'pixels':width*height,'geometry':[x,y,width,height]}


def probe_vice():
    import shadow_boot_probe as sp
    from capability_relocation_probe import inject_until_state
    from vice_capture import choose_port
    from window_completion_probe import window_base
    report=verify_build()
    loader=(PROOF / LOADER_REL).read_text()
    match=re.search(r'^GATE_SOURCE = \$([0-9a-fA-F]+)$',loader,re.M)
    if match is None:raise ValueError('qualified gateway source missing')
    gate_start=int(match.group(1),16)
    gate_size=len((PROOF / 'build/gateway.bin').read_bytes())
    if gate_size!=196 or not 0x4200<=gate_start<=0x5210-gate_size:
        raise ValueError('qualified gateway source range')
    symbols=sp.symbol_addresses(REPO / 'build/8502/udeks-8502.map')
    base=window_base((REPO / 'build/8502/udeks-8502.map').read_text())
    result={}
    for fmt in ('d71','d64'):
        port=choose_port();process,master=sp.launch_vice(WORK / f'udeks-cache.{fmt}',port,'net.sf.VICE')
        try:
            time.sleep(6);deadline=time.monotonic()+180
            sp.wait_for_byte(port,sp.ROOT_TERMINAL_STATUS_READY_ADDRESS,2,deadline)
            for command,address in (('xinit',0xf1b5),('xclock &',0xf225),('xwave &',0xf265)):
                inject_until_state(port,symbols,command,address,3,deadline)
            sp.wait_for_byte(port,report['symbols']['_cache_accept_state'],0x80,deadline)
            # Device NMI source, not patched OS counters or runtime state.
            sp.write_kernel_blocks(port,[(0xdd04,b'\x00\x10'),(0xdd0d,b'\x81\x11')])
            for attempt in range(20):
                sp.wait_for_byte(port,report['symbols']['_cache_phase'],2,deadline)
                blocks=[('shadow',0xa1e0,0xc11f,'kernel'),('bitmap',0x6000,0x7f3f,'worker'),
                    ('image',0x5350,0x5bff,'worker'),('window',base+17,base+33,'kernel'),
                    ('phase',report['symbols']['_cache_phase'],report['symbols']['_cache_phase'],'kernel'),
                    ('source',gate_start,gate_start+gate_size-1,'worker'),('guards',0x5340,0x534f,'worker')]
                raw=sp.capture_blocks(port,[(WORK / f'vice-{fmt}-{name}.bin',start,end,profile)
                                            for name,start,end,profile in blocks])
                data={item[0]:value for item,value in zip(blocks,raw)}
                if data['phase']==b'\x02':break
            else:raise ValueError('no settled VICE capture')
            for name,value in data.items():(WORK / f'vice-{fmt}-{name}.bin').write_bytes(value)
            result[fmt]=bitmap_oracle(data['shadow'],data['bitmap'],data['image'],data['window'])
            if data['source']!=(PROOF / 'build/gateway.bin').read_bytes():
                raise ValueError('immutable gateway source changed')
            if any(data['guards']):raise ValueError('private stack guard overwritten')
            sp.write_kernel_blocks(port,[(0xdd0e,b'\x00')])
            sp.wait_for_byte(port,0xfff5,0,deadline)
            nmi=sp.capture_blocks(port,[(WORK / f'vice-{fmt}-nmi.bin',0xffd0,0xffff,'kernel')])[0]
            (WORK / f'vice-{fmt}-nmi.bin').write_bytes(nmi)
            from nmi_integration_probe import inspect_nmi
            result[fmt].update(inspect_nmi(nmi))
            inject_until_state(port,symbols,'xinit -q',0xf1b5,2,deadline)
            sp.wait_for_byte(port,report['symbols']['_cache_phase'],0,deadline)
            inject_until_state(port,symbols,'xinit',0xf1b5,3,deadline)
            print('VICE '+fmt+': '+json.dumps(result[fmt]),flush=True)
        finally:
            sp.terminate(process,port);os.close(master)
    paths=sorted(WORK.glob('vice-*.bin'))
    verify_build()
    (WORK / 'vice-run.json').write_text(json.dumps({'results':result,
        'provenance':subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True),
        'report_sha256':digest(WORK / 'report.json'),'raw_sha256':{p.name:digest(p) for p in paths},
        'scope':'cold boot, native row capture, pixels, NMI and graphics restart; dragging separately native-tested in 1986'},indent=2)+'\n')


def preserve():
    report=verify_build()
    for engine in ('1986','vice'):
        binding=json.loads((WORK / f'{engine}-run.json').read_text())
        if binding['report_sha256']!=digest(WORK / 'report.json'):
            raise ValueError('stale emulator run '+engine)
        if set(binding['results'])!={'d71','d64'}:raise ValueError('incomplete emulator gate')
        for name,sha in binding['raw_sha256'].items():
            if digest(WORK / name)!=sha:raise ValueError('raw evidence drift '+name)
    native=json.loads((WORK / '1986-run.json').read_text())
    for fmt in ('d71','d64'):
        if digest(WORK / f'1986-{fmt}.log')!=native['results'][fmt]['log_sha256']:
            raise ValueError('native log drift')
    for name in ('native','native.c'):
        key='runner_sha256' if name=='native' else 'source_sha256'
        if digest(WORK / name)!=native[key]:raise ValueError('native runner drift')
    artifact=ROOT / 'bench/artifacts' / NAME
    result=ROOT / 'bench/results' / NAME
    if artifact.exists() or result.exists():raise ValueError('refusing to overwrite evidence')
    for key in ('inputs_sha256','source_sha256'):
        for name in report[key]:
            target=artifact / 'inputs' / name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT / name,target)
    for name in ('report.json','udeks-cache.d71','udeks-cache.d64','native','native.c'):
        target=artifact / 'build' / name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(WORK / name,target)
    result.mkdir(parents=True)
    for pattern in ('1986-*.bin','1986-*.log','vice-*.bin','*-run.json'):
        for path in WORK.glob(pattern):shutil.copy2(path,result / path.name)
    for directory in (artifact,result):
        paths=sorted(p for p in directory.rglob('*') if p.is_file())
        (directory / 'SHA256SUMS').write_text(''.join(
            f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))
    print('Preserved integrated test disks and both-emulator evidence at '+str(artifact))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('build','1986','vice','preserve'))
    action=parser.parse_args().action
    {'build':build,'1986':probe_native,'vice':probe_vice,'preserve':preserve}[action]()

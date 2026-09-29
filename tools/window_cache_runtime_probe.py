#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime-only cache qualification helpers; no private builders or app transforms."""
import hashlib
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/window-cache-integration'
REPO = ROOT
PROOF = WORK / 'delivery'
MODULE_REL = 'build/module.bin'
LOADER_REL = 'build/loader.inc'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_build():
    raise RuntimeError('configure a source-bound integration report first')


def validate_live_slot(slot, module, width, height):
    from build_window_cache import identity
    if len(slot) != 4128 or not 0 < width <= 320 or not 0 < height <= 200:
        raise ValueError('invalid live slot/geometry')
    if module[0x4c:0x4f] != b'\x9d\xff\xff' or module[0x73:0x76] != b'\xbd\xff\xff':
        raise ValueError('qualified row operand layout changed')
    address = 0x5350 + (height - 1) * ((width + 7) // 8)
    for offset in (0x4d, 0x74):
        if int.from_bytes(slot[offset:offset + 2], 'little') != address:
            raise ValueError('last row pointer outside completed image')
    normalized = bytearray(slot)
    for offset in (0x4d, 0x4e, 0x74, 0x75, 0xd1, 0xd2, 0xd3, 0xd4):
        normalized[offset] = module[offset]
    expected = module.ljust(0x1010, b'\0') + identity(module)
    if normalized != expected:
        raise ValueError('delivered module/identity/padding changed')
    return {'bytes': len(module), 'slot_sha256': hashlib.sha256(normalized).hexdigest()}


def probe_native(transform=None):
    from importlib import import_module
    from graphics_raster_bench_run import emulator_provenance
    from window_completion_probe import window_base
    builder=import_module('1986_input_smoke_build')
    report=verify_build()
    emulator=Path(os.environ.get('UDEKS_1986_ROOT', ROOT.parent / '1986'))
    sources=builder.emulator_sources(emulator)
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

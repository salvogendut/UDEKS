#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated compact cache transport experiment; no normal-build mutation."""
import argparse
import json
import subprocess
import shutil
from pathlib import Path
from graphics_span_bench import object_sizes
from graphics_raster_bench_build import function
import window_cache_acceptance as acceptance

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/bench/window-cache-compact'
PROOF=ROOT/'bench/artifacts/2026-09-28-window-cache-controller'
SOURCE=ROOT/'bench/window-cache-compact'
NAME='2026-09-28-window-cache-compact'

def shared_geometry(source):
    """Private fixed request specialization: never copy a record onto itself."""
    old=function(source,'geometry_request').rstrip()
    if source.count(old)!=1:raise ValueError('geometry copy seam changed')
    source=source.replace(old,'static void geometry_request(const struct udeks_cache_geometry *geometry)\n{\n    (void)geometry; /* Caller must supply the shared request record itself. */\n}')
    for old,new in (('!eligible || geometry == 0)',
        '!eligible || geometry != (const struct udeks_cache_geometry *)&GEOMETRY)'),
        ('handle != STATE->handle || geometry == 0 ||',
         'handle != STATE->handle || geometry != (const struct udeks_cache_geometry *)&GEOMETRY ||')):
        if source.count(old)!=1:raise ValueError('geometry precondition seam changed')
        source=source.replace(old,new)
    return source

def measure():
    WORK.mkdir(parents=True,exist_ok=True)
    original=(PROOF/'src/services/window/move_cache_flow.c').read_text()
    path=WORK/'flow.c';path.write_text(shared_geometry(original))
    report=json.loads((PROOF/'build/build-report.json').read_text())
    subprocess.run(['cl65','-t','none','--cpu','6502','-Oirs','--standard','c99',
        '-I',str(ROOT/'include'),*[x for d in report['defines'] for x in ('-D',d)],
        '-c','-o',str(WORK/'flow.o'),str(path)],check=True)
    print(json.dumps({'previous_flow':report['objects']['flow'],
                     'shared_geometry_flow':object_sizes(WORK/'flow.o')},indent=2))

def compact_gateway(source):
    # The resident guard owns interrupt/status preservation across this entire
    # call. The gateway still normalizes D before entering compiled C.
    source=source.replace('command_entry:\n        php\n        sei\n','command_entry:\n')
    source=source.replace('        plp\n        lda RESULT','        lda RESULT')
    # MMU preset strobes select a configuration independently of written data.
    source=source.replace('        lda #$00\n        sta WORKER','        sta WORKER')
    source=source.replace('        lda #$00\n        sta KERNEL','        sta KERNEL')
    start=source.index('        sec\n        lda write_byte+1')
    end=source.index('        ldy OFFSET+1',start)
    source=source[:start]+'''        ; Logical last offset = OFFSET + (RAWCOUNT-1)*8. Two carries
        ; handle a 40-byte row crossing up to two logical page boundaries.
        dex
        txa
        asl a
        asl a
        asl a
        ldy OFFSET+1
        bcc :+
        iny
:
        clc
        adc OFFSET
        bcc :+
        iny
:
        sty last_page+1
'''+source[end:]
    return source

def module_build():
    measure()
    report=json.loads((PROOF/'build/build-report.json').read_text())
    layout=ROOT/'bench/window-cache-controller'
    gateway=WORK/'gateway.s';gateway.write_text(compact_gateway((PROOF/'build/gateway.s').read_text()))
    subprocess.run(['ca65','-I',str(layout),'-o',str(WORK/'gateway.o'),str(gateway)],check=True)
    subprocess.run(['ld65','-C',str(ROOT/'bench/window-cache-c-runtime/gateway.cfg'),
        '-o',str(WORK/'gateway.bin'),str(WORK/'gateway.o')],check=True)
    # Same core, dispatcher, all published ZP addresses and private allocations.
    for name in ('core','module'):
        path=WORK/f'{name}.s';shutil.copy2(PROOF/'build'/f'{name}.s',path)
        subprocess.run(['ca65','-I',str(layout),'-o',str(WORK/f'{name}.o'),str(path)],check=True)
    for name,path in (('policy',PROOF/'src/services/window/move_cache_state.c'),
                      ('command',PROOF/'src/services/window/cache_overlay.c'),
                      ('controller',PROOF/'bench/window-cache-controller/controller.c')):
        subprocess.run(['cl65','-t','none','--cpu','6502','-Oirs','--standard','c99','-I',str(ROOT/'include'),
            *[x for d in report['defines'] for x in ('-D',d)],'-c','-o',str(WORK/f'{name}.o'),str(path)],check=True)
    image=WORK/'gateway-image.s'
    image.write_text('.segment "GATEIMAGE"\n.export cache_gateway_source\ncache_gateway_source:\n'
        f'.incbin "{WORK.relative_to(ROOT)}/gateway.bin"\n')
    subprocess.run(['ca65','-o',str(WORK/'gateway-image.o'),str(image)],check=True)
    cfg=WORK/'module.cfg';cfg.write_text((layout/'module.cfg').read_text().replace(
        '    PRIVATESTATE:', '    GATEIMAGE: load=MODULE, type=ro;\n    PRIVATESTATE:'))
    subprocess.run(['cl65','-t','none','-C',str(cfg),'-m',str(WORK/'module.map'),'-o',str(WORK/'module.bin'),
        *[str(WORK/f'{n}.o') for n in ('core','module','policy','command','flow','controller','gateway-image')]],check=True)
    data=(WORK/'module.bin').read_bytes()
    if len(data)>0x1010:raise ValueError('module reaches VCC2 identity')
    if data[:213]!=(PROOF/'build/module.bin').read_bytes()[:213]:raise ValueError('row core changed')
    from placement_audit import parse_map
    source=next(s for n,s,e in parse_map((WORK/'module.map').read_text())[1] if n=='GATEIMAGE')
    print(json.dumps({'module_bytes':len(data),'gateway_bytes':len((WORK/'gateway.bin').read_bytes()),
        'gateway_source':source,'identity_slack':0x1010-len(data)},indent=2))
    return source

def configure():
    acceptance.WORK=WORK/'acceptance'
    acceptance.NAME=NAME

def live_faults(normal,gate,symbols,faults):
    # Fault the copied gateway after acceptance, not its checksummed source.
    # Both baseline immediate stores reproduce original bytes exactly.
    offset=symbols['_cache_copy_fault_probe'][0]-0x2000+2
    if normal[offset:offset+2]!=bytes((0xa9,6)) or normal[offset+5:offset+7]!=bytes((0xa9,0x53)):
        raise ValueError('diagnostic postcopy patch changed')
    faults.update({'zp-leak':offset+1,'shell-stack':offset+6})
    return faults

def build():
    source=module_build();configure();acceptance.WORK.mkdir(parents=True,exist_ok=True)
    gate=(WORK/'gateway.bin').read_bytes()
    restore=bytes.fromhex('689506e8');stack=bytes.fromhex('a9538507')
    if gate.count(restore)!=1 or gate.count(stack)!=1:raise ValueError('ambiguous gateway patches')
    diag=('\n.segment "CODE"\n.export _cache_copy_fault_probe\n_cache_copy_fault_probe:\n'
        f'        lda #$06\n        sta ${0xf68a+gate.index(restore)+2:04x}\n'
        f'        lda #$53\n        sta ${0xf68a+gate.index(stack)+1:04x}\n        rts\n')
    constants=acceptance.WORK/'loader.inc'
    constants.write_text(f'GATE_SOURCE = ${source:04x}\nGATE_BYTES = ${len(gate):02x}\n')
    inputs=[Path(__file__),SOURCE/'raw.s',constants,WORK/'flow.c',WORK/'module.cfg',
        WORK/'module.bin',WORK/'module.map',WORK/'gateway.s',WORK/'gateway.bin',
        WORK/'gateway-image.s',WORK/'core.s',WORK/'module.s',
        PROOF/'src/services/window/move_cache_flow.c',PROOF/'src/services/window/move_cache_state.c',
        PROOF/'src/services/window/cache_overlay.c',PROOF/'bench/window-cache-controller/controller.c']
    inputs += [ROOT/'include/udeks'/n for n in ('window_cache_flow.h','window_cache_command.h','window_cache_state.h')]
    inputs += [ROOT/'tests/test_window_cache_compact.py']
    inputs += [PROOF/'build'/n for n in ('build-report.json','gateway.s','core.s','module.s')]
    inputs += [ROOT/'bench/window-cache-controller/module.cfg',ROOT/'tools/graphics_span_bench.py',
        ROOT/'tools/graphics_raster_bench_build.py',ROOT/'tools/placement_audit.py',ROOT/'tools/gen_capability_imports.py']
    acceptance.build(module_path=WORK/'module.bin',gateway_path=WORK/'gateway.bin',
        raw_template=(SOURCE/'raw.s').read_text(),extra_driver=diag,extra_inputs=inputs,fault_selector=live_faults)
    path=acceptance.WORK/'build-report.json';report=json.loads(path.read_text())
    report['qualification']='standalone compact validated transport; no normal delivery or GUI hooks'
    # Diagnostic hook is kept fully charged, not hidden in the benchmark driver.
    report['diagnostic_patch_bytes']=11;report['resident_bytes']+=11
    report['remaining_before_hooks']=report['available']-report['resident_bytes']
    report['gateway_bytes']=len(gate);report['gateway_source']=source
    report['flow_bytes']=object_sizes(WORK/'flow.o')['CODE']
    report['defines']=json.loads((PROOF/'build/build-report.json').read_text())['defines']
    report['cc65']=subprocess.check_output(['cc65','--version'],stderr=subprocess.STDOUT,text=True).strip()
    report['identity_slack']=0x1010-len((WORK/'module.bin').read_bytes())
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if not k.endswith('sha256')},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('measure','module','build','run','preserve'))
    parser.add_argument('--engine',choices=('1986','vice'))
    parser.add_argument('--output',type=Path,default=ROOT/'build/bench/window-cache-compact-results')
    args=parser.parse_args()
    if args.action=='measure':measure()
    elif args.action=='module':module_build()
    elif args.action=='build':build()
    else:
        configure()
        if args.action=='run':acceptance.run(args.engine,args.output)
        else:acceptance.preserve(args.output)

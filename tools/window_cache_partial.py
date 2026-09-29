#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private prefix/row-range cache experiment; never changes the normal build."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import window_cache_compact as compact
from graphics_span_bench import object_sizes
from placement_audit import parse_map

ROOT = compact.ROOT
WORK = ROOT / 'build/bench/window-cache-partial'
NAME = '2026-09-29-window-cache-partial'
BASE_DECODE = compact.acceptance.decode
BASE_NEGATIVE = compact.acceptance.negative


def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError('partial cache seam changed: ' + old[:70])
    return source.replace(old, new)


def fixed_policy(source):
    """Same policy, one private lease; wrong pointers still reject atomically."""
    source = replace(source, '#include "udeks/window_cache_state.h"', '''#include "udeks/window_cache_state.h"
#ifdef UDEKS_CACHE_COMMAND_HOST_TEST
extern struct udeks_cache_lease cache_test_lease;
#define FIXED (&cache_test_lease)
#else
#define FIXED ((struct udeks_cache_lease *)UDEKS_CACHE_LEASE_ADDRESS)
#endif''')
    source = source.replace('lease->', 'FIXED->')
    source = replace(source, 'return owner != 0', 'return lease == FIXED && owner != 0')
    source = replace(source, '    FIXED->geometry.x = 0;',
                     '    if (lease != FIXED) return;\n    FIXED->geometry.x = 0;')
    source = replace(source, '    if (owner == 0 || FIXED->owner == owner)',
                     '    if (lease != FIXED) return;\n    if (owner == 0 || FIXED->owner == owner)')
    source = replace(source, '    if (owner == 0 || owner > 4u',
                     '    if (lease != FIXED || owner == 0 || owner > 4u')
    return source


def command(source):
    source = replace(source, 'cache_test_params[9]', 'cache_test_params[14]')
    source = replace(source, 'extern void udeks_cache_overlay_row(void);', '''extern void udeks_cache_overlay_row(void);
/* Three initialized DATA bytes, inside the checksummed module allocation.
 * Full-image geometry/stride remains authoritative for source addressing. */
uint8_t cache_partial_end = 0;
uint16_t cache_partial_width = 0;''')
    source = replace(source, '        udeks_cache_init(LEASE, UDEKS_CACHE_IMAGE_CAPACITY);',
                     '        cache_partial_end = 0; cache_partial_width = 0;\n'
                     '        udeks_cache_init(LEASE, UDEKS_CACHE_IMAGE_CAPACITY);')
    source = replace(source, '        udeks_cache_invalidate(LEASE, OWNER);',
                     '        udeks_cache_invalidate(LEASE, OWNER);\n'
                     '        if (LEASE->phase == UDEKS_CACHE_EMPTY) {\n'
                     '            cache_partial_end = 0; cache_partial_width = 0;\n        }')
    source = replace(source, '    case UDEKS_CACHE_COMMAND_STEP:\n', '''    case UDEKS_CACHE_COMMAND_STEP:
        if (LEASE->phase == UDEKS_CACHE_PASTING &&
            (cache_partial_end <= LEASE->row ||
             cache_partial_end > LEASE->geometry.height ||
             cache_partial_width == 0 ||
             cache_partial_width > LEASE->geometry.width))
            return UDEKS_CACHE_INVALID;
''')
    source = replace(source, '        address = UDEKS_CACHE_IMAGE_ADDRESS + ROW->image_offset;', '''        if (ROW->mode) {
            ROW->stride = (cache_partial_width + 7u) >> 3;
            ROW->raw_count = (cache_partial_width + ROW->shift + 7u) >> 3;
            ROW->last_mask = (cache_partial_width & 7u) ?
                (uint8_t)(255u << (8u - (cache_partial_width & 7u))) : 255u;
        }
        address = UDEKS_CACHE_IMAGE_ADDRESS + ROW->image_offset;''')
    source = replace(source, '        return UDEKS_CACHE_COMMAND_SUCCESS | written | LEASE->phase;', '''        if (ROW->mode && LEASE->row == cache_partial_end)
            LEASE->phase = UDEKS_CACHE_READY;
        return UDEKS_CACHE_COMMAND_SUCCESS | written | LEASE->phase;''')
    source = replace(source, '    return UDEKS_CACHE_COMMAND_SUCCESS | LEASE->phase;', '''    if (command == UDEKS_CACHE_COMMAND_PASTE) {
        cache_partial_end = LEASE->geometry.height;
        cache_partial_width = LEASE->geometry.width;
    } else if (command == UDEKS_CACHE_COMMAND_CAPTURE) {
        cache_partial_end = 0; cache_partial_width = 0;
    }
    return UDEKS_CACHE_COMMAND_SUCCESS | LEASE->phase;''')
    return source


def controller(source):
    source = replace(source, 'uint8_t __fastcall__ udeks_cache_controller', '''/* Private command protocol 0.2: op 6 uses PARAM[10..13].
 * Existing commands and the VCC2 envelope layout are unchanged. */
extern uint8_t cache_partial_end;
extern uint16_t cache_partial_width;
#ifdef UDEKS_CACHE_CONTROLLER_HOST_TEST
extern struct udeks_cache_lease cache_test_lease;
extern uint8_t cache_test_params[14];
#define LEASE (&cache_test_lease)
#define PARAM cache_test_params
#else
#define LEASE ((struct udeks_cache_lease *)UDEKS_CACHE_LEASE_ADDRESS)
#define PARAM ((volatile uint8_t *)0xF780u)
#endif
uint8_t __fastcall__ udeks_cache_controller''')
    source = replace(source, '    uint8_t status;', '    uint8_t status;\n    uint16_t width;')
    source = replace(source, '    case UDEKS_CACHE_COMMAND_STEP:', '''    case 6: /* PREFIX: [first,end), prefix width; no source left-edge shift. */
        width = (uint16_t)PARAM[12] | ((uint16_t)PARAM[13] << 8);
        if (PARAM[10] >= PARAM[11] || PARAM[11] > GEOMETRY->height ||
            width == 0 || width > GEOMETRY->width)
            return UDEKS_CACHE_INVALID;
        status = udeks_cache_flow_paste(FLOW, OWNER, GEOMETRY);
        if (status == UDEKS_CACHE_OK) {
            LEASE->row = PARAM[10];
            cache_partial_end = PARAM[11];
            cache_partial_width = width;
        }
        break;
    case UDEKS_CACHE_COMMAND_STEP:''')
    return source


def generate():
    WORK.mkdir(parents=True, exist_ok=True)
    providers = {
        'policy': fixed_policy((ROOT/'src/services/window/move_cache_state.c').read_text()),
        'command': command((ROOT/'src/services/window/cache_overlay.c').read_text()),
        'flow': compact.shared_geometry((ROOT/'src/services/window/move_cache_flow.c').read_text()),
        'controller': controller((ROOT/'bench/window-cache-controller/controller.c').read_text()),
    }
    for name, source in providers.items():
        (WORK/(name+'.c')).write_text(source)
    return providers


def build():
    for proof in (compact.PROOF,ROOT/'bench/artifacts/2026-09-28-window-cache-compact'):
        for line in (proof/'SHA256SUMS').read_text().splitlines():
            sha,name=line.split('  ',1)
            if compact.acceptance.digest(proof/name)!=sha:
                raise ValueError('qualified input drift '+name)
    generate()
    proof = compact.PROOF
    layout = ROOT/'bench/window-cache-controller'
    defines = json.loads((proof/'build/build-report.json').read_text())['defines']
    for name in ('policy', 'command', 'flow', 'controller'):
        subprocess.run(['cl65','-t','none','--cpu','6502','-Oirs','--standard','c99',
            '-I',str(ROOT/'include'),*[x for d in defines for x in ('-D',d)],
            '-c','-o',str(WORK/(name+'.o')),str(WORK/(name+'.c'))],check=True)
    for name in ('core', 'module'):
        shutil.copy2(proof/'build'/(name+'.s'),WORK/(name+'.s'))
    (WORK/'gateway.s').write_text(compact.compact_gateway((proof/'build/gateway.s').read_text()))
    for name in ('core','module','gateway'):
        subprocess.run(['ca65','-I',str(layout),'-o',str(WORK/(name+'.o')),
                        str(WORK/(name+'.s'))],check=True)
    subprocess.run(['ld65','-C',str(ROOT/'bench/window-cache-c-runtime/gateway.cfg'),
        '-o',str(WORK/'gateway.bin'),str(WORK/'gateway.o')],check=True)
    (WORK/'gateway-image.s').write_text('.segment "GATEIMAGE"\n.export cache_gateway_source\n'
        f'cache_gateway_source:\n.incbin "{WORK.relative_to(ROOT)}/gateway.bin"\n')
    subprocess.run(['ca65','-o',str(WORK/'gateway-image.o'),str(WORK/'gateway-image.s')],check=True)
    (WORK/'module.cfg').write_text((layout/'module.cfg').read_text().replace(
        '    PRIVATESTATE:', '    GATEIMAGE: load=MODULE, type=ro;\n    PRIVATESTATE:'))
    subprocess.run(['cl65','-t','none','-C',str(WORK/'module.cfg'),'-m',str(WORK/'module.map'),
        '-o',str(WORK/'module.bin'),*[str(WORK/(n+'.o')) for n in
        ('core','module','policy','command','flow','controller','gateway-image')]],check=True)
    data = (WORK/'module.bin').read_bytes()
    gate = (WORK/'gateway.bin').read_bytes()
    old = ROOT/'bench/artifacts/2026-09-28-window-cache-compact/build'
    if data[:213] != (proof/'build/module.bin').read_bytes()[:213]:
        raise ValueError('qualified row core changed')
    if gate != (old/'gateway.bin').read_bytes():
        raise ValueError('qualified common gateway changed')
    if len(data) > 0x1010:
        raise ValueError('module reaches identity')
    segments = parse_map((WORK/'module.map').read_text())[1]
    if next(e-s+1 for n,s,e in segments if n=='DATA') != 3:
        raise ValueError('partial metadata must be exactly three charged bytes')
    report = {'module_bytes':len(data),'identity_slack':0x1010-len(data),
        'gateway_source':next(s for n,s,e in segments if n=='GATEIMAGE'),
        'gateway_bytes':len(gate),'private_data_bytes':3,
        'objects':{n:object_sizes(WORK/(n+'.o')) for n in ('policy','command','flow','controller')}}
    (WORK/'module-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


def probe(source):
    old = '    geometry(xx,yy,w,h);check(call(3,1,0)==0,15);drive(1,h);++images;'
    return replace(source, old, '''    geometry(xx,yy,w,h);
#if CASE == 1
    /* Bad range requests must not consume the READY image. */
    V(0xF78A)=17;V(0xF78B)=67;W(0xF78C)=0;
    check(call(6,1,0)==1,24);
    W(0xF78C)=169;check(call(6,1,0)==1,24);
    W(0xF78C)=52;V(0xF78A)=67;check(call(6,1,0)==1,24);
    V(0xF78A)=17;V(0xF78B)=105;check(call(6,1,0)==1,24);
    V(0xF78B)=67;check(call(6,2,0)==1,24);
    geometry(320,yy,w,h);check(call(6,1,0)==1,24);
    geometry(xx,yy,w,h);
    check(call(6,1,0)==0,15);drive(1,50);
#else
    /* Exercise all source/destination bit alignments with a short prefix. */
    V(0xF78A)=0;V(0xF78B)=h;W(0xF78C)=(w+1u)/2u;
    check(call(6,1,0)==0,15);drive(1,h);
#endif
    ++images;''')


def reference(case):
    """Independent logical pixels and touched destination pages, not row math."""
    original=bytes((i*13+7)&255 for i in range(8000))
    bitmap=bytearray(((i*31+19)&255 if case else original[i]) for i in range(8000))
    dirty=bytearray(32)
    rectangles=([(a,128,b,a*8+b,9,0,1) for a in range(8) for b in range(8)] +
                [(0,129,0,64,160,0,1),(319,199,319,199,1,0,1)] if case==0 else
                [(7,7,100,40,52,17,67),(7,7,151,83,168,0,104)])
    for sx,sy,dx,dy,width,first,end in rectangles:
        for y in range(first,end):
            for x in range(width):
                so=((sy+y)//8)*320+((sx+x)//8)*8+(sy+y)%8
                dest=((dy+y)//8)*320+((dx+x)//8)*8+(dy+y)%8
                mask=128>>((dx+x)%8)
                bitmap[dest]=(bitmap[dest]&~mask) | (mask if original[so]&(128>>((sx+x)%8)) else 0)
                dirty[dest//256]=1
    return bytes(bitmap+dirty)


def normalize(data,case):
    if len(data)!=8096 or data[64:]!=reference(case):
        raise ValueError('partial prefix pixel/dirty oracle failed')
    expected_rows,expected_calls=(132,480) if case==0 else (258,289)
    if int.from_bytes(data[8:10],'little')!=expected_rows or int.from_bytes(data[10:12],'little')!=expected_calls:
        raise ValueError('partial continuation rows/commands')
    normal=bytearray(data)
    normal[8:10]=(132 if case==0 else 312).to_bytes(2,'little')
    normal[10:12]=(480 if case==0 else 337).to_bytes(2,'little')
    normal[64:]=compact.acceptance.controller.base.reference(case)
    return normal


def decode(data,case,pages=16):
    value=BASE_DECODE(normalize(data,case),case,pages)
    value.update(rows=132 if case==0 else 258,commands=480 if case==0 else 289,
                 pixel_sha256=compact.acceptance.controller.digest_bytes(data[64:]))
    return value


def negative(data,name,pages=16):
    if name in ('bad-code','bad-header'):return BASE_NEGATIVE(data,name,pages)
    value=BASE_NEGATIVE(normalize(data,0),name,pages)
    value['pixel_sha256']=compact.acceptance.controller.digest_bytes(data[64:])
    return value


def configure():
    acceptance=compact.acceptance
    acceptance.WORK=WORK/'acceptance'
    acceptance.NAME=NAME
    acceptance.decode=decode
    acceptance.negative=negative


def qualify_build():
    build(); configure()
    acceptance=compact.acceptance
    acceptance.WORK.mkdir(parents=True,exist_ok=True)
    report=json.loads((WORK/'module-report.json').read_text())
    gate=(WORK/'gateway.bin').read_bytes()
    restore=bytes.fromhex('689506e8');stack=bytes.fromhex('a9538507')
    if gate.count(restore)!=1 or gate.count(stack)!=1:raise ValueError('diagnostic patches')
    diag=('\n.segment "CODE"\n.export _cache_copy_fault_probe\n_cache_copy_fault_probe:\n'
        f'        lda #$06\n        sta ${0xf68a+gate.index(restore)+2:04x}\n'
        f'        lda #$53\n        sta ${0xf68a+gate.index(stack)+1:04x}\n        rts\n')
    constants=acceptance.WORK/'loader.inc'
    constants.write_text(f'GATE_SOURCE = ${report["gateway_source"]:04x}\nGATE_BYTES = ${len(gate):02x}\n')
    inputs=[Path(__file__),ROOT/'tests/test_window_cache_partial.py',
        ROOT/'bench/window-cache-controller/partial-host.c',constants,compact.SOURCE/'raw.s',
        ROOT/'tools/window_cache_compact.py',ROOT/'tools/graphics_span_bench.py',
        ROOT/'tools/graphics_raster_bench_build.py',ROOT/'tools/placement_audit.py',
        ROOT/'tools/gen_capability_imports.py',ROOT/'bench/window-cache-controller/module.cfg',
        compact.PROOF/'build/build-report.json',compact.PROOF/'build/gateway.s',
        compact.PROOF/'build/core.s',compact.PROOF/'build/module.s']
    inputs += [ROOT/'src/services/window'/n for n in ('move_cache_state.c','cache_overlay.c','move_cache_flow.c')]
    inputs += [ROOT/'include/udeks'/n for n in ('window_cache_state.h','window_cache_command.h','window_cache_flow.h')]
    inputs += [WORK/n for n in ('policy.c','command.c','flow.c','controller.c','module.cfg','module.map',
        'module.bin','gateway.bin','gateway.s','gateway-image.s','module.s','core.s','module-report.json')]
    acceptance.build(module_path=WORK/'module.bin',gateway_path=WORK/'gateway.bin',
        raw_template=(compact.SOURCE/'raw.s').read_text(),extra_driver=diag,
        extra_inputs=inputs,fault_selector=compact.live_faults,probe_transform=probe)
    path=acceptance.WORK/'build-report.json'
    result=json.loads(path.read_text())
    result.update(qualification='standalone prefix/row-range command 0.2; no GUI hooks',
        private_data_bytes=3,gateway_source=report['gateway_source'],gateway_bytes=len(gate),
        diagnostic_patch_bytes=11,resident_bytes=result['resident_bytes']+11)
    result['remaining_before_hooks']=result['available']-result['resident_bytes']
    path.write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('generate','build','qualify','run','preserve'))
    parser.add_argument('--engine',choices=('1986','vice'))
    parser.add_argument('--output',type=Path,default=ROOT/'build/bench/window-cache-partial-results')
    args = parser.parse_args()
    if args.action=='generate':generate()
    elif args.action=='build':build()
    elif args.action=='qualify':qualify_build()
    else:
        configure()
        if args.action=='run':compact.acceptance.run(args.engine,args.output)
        else:compact.acceptance.preserve(args.output)

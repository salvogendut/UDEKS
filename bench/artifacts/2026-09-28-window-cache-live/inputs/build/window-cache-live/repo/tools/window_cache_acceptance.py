#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify page-bounded acceptance before calling the bank-1 C controller."""
import argparse
import hashlib
import importlib
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
import window_cache_controller as controller
from window_cache_controller_delivery import fixture

ROOT = controller.ROOT
WORK = ROOT / 'build/bench/window-cache-acceptance'
SOURCE = ROOT / 'bench/window-cache-acceptance'
PROOF = ROOT / 'bench/artifacts/2026-09-28-window-cache-controller'
NAME = '2026-09-28-window-cache-acceptance'
CASES = (0, 1, 'bad-code', 'bad-header', 'irq-leak', 'zp-leak', 'shell-stack', 'no-pending')

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def page_geometry(length):
    if length<=0:raise ValueError('empty module')
    return ((length-1)//256,(length-1)%256+1,(length+255)//256)

def private_state(case):
    lease = bytearray(13); lease[8:10] = (2224).to_bytes(2,'little')
    row = (bytes.fromhex('3f1f00000101078001') if case == 0 else
           bytes.fromhex('521d7308151607ff01'))
    return bytes(lease) + row + (69 if case == 0 else 4).to_bytes(2,'little') + b'\0\0'

def decode(data, case, pages=16):
    if len(data)!=8096 or data[:4]!=b'AVLD': raise ValueError('acceptance header')
    if data[38:64]!=private_state(case): raise ValueError('persistent controller state')
    normal=bytearray(data);normal[:4]=b'CTRL';normal[38:64]=bytes(26)
    calls=480 if case==0 else 337
    if int.from_bytes(normal[10:12],'little')!=calls: raise ValueError('acceptance command count')
    normal[10:12]=(calls-4).to_bytes(2,'little')
    return {**controller.decode(normal,case),'commands':calls,'acceptance_pages':pages}

def negative(data,name,pages=16):
    if name in ('bad-code','bad-header'):
        if len(data)!=8096 or data[:8]!=b'AVLD\x01\x02\x00\x00':
            raise ValueError('rejection header/semantic failure')
        if any(data[8:10]) or data[10:12]!=b'\x06\0' or data[14] or any(data[15:22]):
            raise ValueError('rejected module executed or guard failure')
        if data[22:24]!=b'\xf0\x0f' or any(data[36:38]) or data[38:64]!=bytes([0x6d])*26 or any(data[64:]):
            raise ValueError('rejected module changed private state/stack/pixels')
        irq=int.from_bytes(data[12:14]+data[24:26],'little')
        total=int.from_bytes(data[26:30],'little');worker=int.from_bytes(data[30:34],'little')
        drains=int.from_bytes(data[34:36],'little')
        if not irq or not 0<=worker<total<65536 or total!=drains:
            raise ValueError('rejection IRQ/NMI failure')
        return {'rejected':name,'acceptance_pages':pages if name=='bad-code' else 1,
            'commands':6,'rows':0,'interrupts':irq,'nmi_total':total,
            'nmi_worker_flat':worker,'nmi_drains':drains,'private_state_unchanged':True}
    if len(data)!=8096 or data[:4]!=b'AVLD' or data[38:64]!=private_state(0):
        raise ValueError('fault controller state/header')
    normal=bytearray(data);normal[:4]=b'CTRL';normal[38:64]=bytes(26)
    if normal[10:12]!=(480).to_bytes(2,'little'): raise ValueError('fault command count')
    normal[10:12]=(476).to_bytes(2,'little')
    return {**controller.negative(normal,name),'commands':480,'acceptance_pages':pages}

def clone_oracle(driver, entry, target, counter):
    body = driver[driver.index('_runtime_call:\n'):driver.index('flag_modes:')]
    labels = re.findall(r'^(\w+):', body, re.M)
    for name in sorted(labels, key=len, reverse=True):
        body = re.sub(r'\b'+name+r'\b', name+'_'+entry, body)
    body = body.replace('_runtime_call_'+entry+':', '_runtime_'+entry+':')
    body = body.replace('jsr _private_cache_policy_call', 'jsr '+target)
    if entry == 'accept':
        body = body[:body.index('        lda RETURN_SP')] + body[body.index('sw_ok_'+entry+':')+len('sw_ok_'+entry+':'):]
        body = body.replace('_runtime_call_count', counter)
    return body

def build(module_path=None,gateway_path=None,raw_template=None,extra_driver='',
          extra_inputs=(),fault_selector=None):
    from graphics_span_bench import object_sizes
    from placement_audit import parse_map
    WORK.mkdir(parents=True, exist_ok=True)
    for line in (PROOF / 'SHA256SUMS').read_text().splitlines():
        sha, n = line.split('  ',1)
        if digest(PROOF / n) != sha: raise ValueError('qualified source drift '+n)
    module = (module_path or PROOF / 'build/module.bin').read_bytes()
    last_page,last_bytes,pages=page_geometry(len(module))
    slot = fixture(module)
    (WORK / 'module-envelope.bin').write_bytes(slot.ljust(0x1100,b'\0'))
    header = slot[0x1010:0x1020]
    constants = (f'CACHE_LAST_PAGE = ${last_page:02x}\n'
        f'CACHE_LAST_BYTES = ${last_bytes&255:02x}\nCACHE_CHECKSUM = ${sum(module)&65535:04x}\n'
        '.macro CACHE_EXPECTED_HEADER\n.byte '+','.join(f'${b:02x}' for b in header)+'\n.endmacro\n')
    (WORK / 'acceptance.inc').write_text(constants)
    layout = ROOT / 'bench/window-cache-controller'
    subprocess.run(['ca65','-I',str(WORK),'-I',str(layout),'-o',str(WORK / 'validator.o'),str(SOURCE / 'validator.s')],check=True)
    subprocess.run(['ld65','-C',str(controller.base.OLD / 'gateway.cfg'),'-o',str(WORK / 'validator.bin'),str(WORK / 'validator.o')],check=True)
    shutil.copy2(gateway_path or PROOF / 'build/gateway.bin',WORK / 'gateway.bin')
    if raw_template is None:
        raw = (PROOF / 'build/binding.s').read_text().replace('_private_cache_policy_call','_cache_raw_call')
        raw = raw.replace('build/bench/window-cache-controller/gateway.bin',str((WORK/'gateway.bin').relative_to(ROOT)))
        raw = raw.replace('.export _cache_raw_call','.import _udeks_nmi_drain\n        .export _cache_raw_call')
        raw = raw.replace('        plp\n        jmp RUN','        jsr _udeks_nmi_drain\n        plp\n        jmp RUN')
    else:raw=raw_template
    (WORK / 'raw.s').write_text(raw)
    driver = (PROOF / 'build/driver.s').read_text()
    extra = clone_oracle(driver,'accept','_cache_accept_poll','_runtime_accept_count')
    extra += clone_oracle(driver,'step','_cache_step','_runtime_call_count')
    driver = driver.replace('flag_modes:',extra+'flag_modes:',1)
    driver = driver.replace('.import _udeks_nmi_drain',
        '.import _cache_accept_poll, _cache_step, _cache_accept_state\n'
        '        .export _runtime_accept, _runtime_accept_count, _runtime_step\n        .import _udeks_nmi_drain')
    driver = driver.replace('_runtime_call_count: .res 2','_runtime_call_count: .res 2\n_runtime_accept_count: .res 2')
    driver = driver.replace('build/bench/window-cache-controller/module-envelope.bin',str((WORK/'module-envelope.bin').relative_to(ROOT)))
    driver = driver.replace('        sta $41ff',
        '        sta $41ff\n        ldx #$19\n        lda #$6d\nprivate_markers:\n'
        '        sta LEASE,x\n        dex\n        bpl private_markers')
    driver = driver.replace('\nscan:\n',
        '\nscan:\n        lda #$00\n        sta WORKER\n        ldx #$19\nsnapshot_private:\n'
        '        lda LEASE,x\n        sta STAGE,x\n        dex\n        bpl snapshot_private\n',1)
    # Extended diagnostic blocks exceed the old signed-X (<128) copy limit.
    for name in ('seed','scan'):
        old=(f'        ldx #{name}_end-{name}-1\ninstall_{name}:\n'
             f'        lda {name},x\n        sta RUN,x\n        dex\n        bpl install_{name}')
        new=(f'        ldx #$00\ninstall_{name}:\n'
             f'        lda {name},x\n        sta RUN,x\n        inx\n'
             f'        cpx #{name}_end-{name}\n        bcc install_{name}')
        if driver.count(old)!=1:raise ValueError('diagnostic copy seam '+name)
        driver=driver.replace(old,new)
    driver=driver.replace('        lda RETURN_SP\n',
        '        lda _cache_accept_state\n        cmp #$80\n        bne sw_ok\n        lda RETURN_SP\n',1)
    (WORK / 'driver.s').write_text(driver+extra_driver)
    binding=(SOURCE/'binding.s').read_text().replace('build/bench/window-cache-acceptance/validator.bin',
        str((WORK/'validator.bin').relative_to(ROOT)))
    (WORK/'binding.s').write_text(binding)
    # Avoid phase-locking CIA2's period to the 512-cycle diagnostic IRQ.
    observer=(ROOT/'bench/window-cache-nmi/probe.s').read_text().replace(
        'lda #$04                ; CIA2 Timer A', 'lda #$03                ; CIA2 Timer A')
    (WORK/'observer.s').write_text(observer)
    for n,p in (('binding',WORK / 'binding.s'),('raw',WORK / 'raw.s'),('driver',WORK / 'driver.s'),
        ('launcher',PROOF / 'build/launcher.s'),('nmi',ROOT / 'src/8502/nmi.s'),
        ('observer',WORK / 'observer.s')):
        subprocess.run(['ca65','-I',str(WORK),'-I',str(layout),'-I',str(ROOT / 'src/8502'),
            '-o',str(WORK / (n+'.o')),str(p)],check=True)
    source = (ROOT / 'bench/window-cache-controller/probe.c').read_text()
    source = ('extern unsigned char runtime_accept(void), runtime_step(void);\n'
        'extern unsigned int runtime_accept_count;\n'
        'extern volatile unsigned char cache_accept_state,cache_owner,cache_phase;\n'
        'extern volatile unsigned int cache_ticket;\n'+source)
    source = source.replace("V(RECORD)='C';V(RECORD+1)='T';V(RECORD+2)='R';V(RECORD+3)='L';",
        "V(RECORD)='A';V(RECORD+1)='V';V(RECORD+2)='L';V(RECORD+3)='D';")
    source = source.replace('check(call(4,1,ticket)==0',
        'V(0xF792)=4;W(0xF793)=0xbeef;V(0xF791)=0xff;\n'
        '        check(runtime_step()==0')
    old = 'runtime_install();runtime_irq_start();nmi_probe_start();preflight();'
    warmup = '''runtime_install();runtime_irq_start();nmi_probe_start();
    /* No C call before acceptance, across all four caller I/D modes. */
    for(i=0;i<4;++i)check(call(0,0,0)==0xff,21);
    for(i=0;i<16;++i) {
        unsigned char result=runtime_accept();
        if(result)break;
        /* Simulate an intervening VIC workspace user between pages. */
        runtime_check_memory();
        V(0xF780)=0xa5;V(0xF781)=0x5a;V(0xF782)=0xa5;
    }
#if BADCASE
    check(cache_accept_state==0xff,22);
    check(runtime_accept_count==(BADCASE==2?1u:16u),22);
    check(call(0,0,0)==0xff && call(4,1,1)==0xff,23);
    for(j=0;j<8000;++j)V(SHADOW+j)=0;
    for(i=0;i<32;++i)V(DIRTY+i)=0;
    goto finish;
#else
    check(cache_accept_state==0x80 && runtime_accept_count==16,22);
    check(cache_ticket==1 && cache_owner==0 && cache_phase==0,22);
    preflight();
#endif'''
    warmup=warmup.replace('i<16','i<'+str(pages)).replace('16u',str(pages)+'u').replace(
        'runtime_accept_count==16','runtime_accept_count=='+str(pages))
    if source.count(old)!=1: raise ValueError('controller startup seam changed')
    source = source.replace(old,warmup)
    source = source.replace('    runtime_check_memory();\n    for(j=0;j<736',
        'finish:\n    runtime_check_memory();\n    for(j=0;j<26;++j)V(RECORD+38+j)=V(0xF7B0+j);\n    for(j=0;j<736')
    (WORK / 'probe.c').write_text(source)
    rejection_controls={}
    for case,badcase in ((0,0),(1,0),('bad-code',1),('bad-header',2)):
        stem = WORK / f'probe-{case}'
        subprocess.run(['cl65','-t','none','--standard','c99','-Oirs','-D',f'CASE={case if isinstance(case,int) else 0}',
            '-D',f'BADCASE={badcase}','-c','-o',str(stem.with_suffix('.o')),str(WORK / 'probe.c')],check=True)
        subprocess.run(['cl65','-t','none','-C',str(controller.base.OLD / 'probe.cfg'),
            '-m',str(stem.with_suffix('.map')),'-o',str(stem.with_suffix('.bin')),
            *[str(WORK / (n+'.o')) for n in ('launcher',f'probe-{case}','driver','raw','binding','nmi','observer')]],check=True)
        data = bytearray(b'\x00\x20'+stem.with_suffix('.bin').read_bytes())
        if badcase:
            (WORK/f'probe-{case}.original.prg').write_bytes(data)
            if data.count(slot)!=1:raise ValueError('ambiguous module slot')
            offset=data.index(slot)+(len(module)-1 if badcase==1 else 0x1014)
            rejection_controls[case]={'offset':offset,'before':data[offset],'after':data[offset]^1}
            data[offset]^=1
        stem.with_suffix('.prg').write_bytes(data)
    normal=(WORK / 'probe-0.prg').read_bytes(); gate=(WORK / 'gateway.bin').read_bytes()
    from gen_capability_imports import map_exports
    symbols=map_exports((WORK / 'probe-0.map').read_text())
    faults={'irq-leak':symbols['_cache_accept_poll'][0]-0x2000+3}
    for name,pattern,delta in (('zp-leak',b'\x68\x95\x06\xe8',2),('shell-stack',b'\xa9\x53\x85\x07',1)):
        if gate.count(pattern)!=1 or normal.count(gate)!=1:raise ValueError('ambiguous fault '+name)
        faults[name]=normal.index(gate)+gate.index(pattern)+delta
    stub=bytes.fromhex('48a9018df5ff6840')
    if normal.count(stub)!=1:raise ValueError('ambiguous NMI stub')
    faults['no-pending']=normal.index(stub)+3
    if fault_selector is not None:faults=fault_selector(normal,gate,symbols,faults)
    controls={}
    for name,offset in faults.items():
        bad=bytearray(normal);before=bad[offset];after={'irq-leak':0xea,'zp-leak':7,'shell-stack':0xef,'no-pending':0x2c}[name]
        if name=='irq-leak' and before!=0x78:raise ValueError('acceptance SEI moved')
        bad[offset]=after;(WORK / f'probe-{name}.prg').write_bytes(bad)
        controls[name]={'offset':offset,'before':before,'after':after}
    sizes={n:object_sizes(WORK / (n+'.o')) for n in ('raw','binding','validator')}
    resident=sizes['raw']['CODE']+sizes['binding']['CODE']
    paths=list(SOURCE.iterdir())+[Path(__file__),ROOT / 'bench/window-cache-controller/layout.inc',
        ROOT / 'bench/window-cache-controller/probe.c',ROOT / 'tools/window_cache_controller.py',
        ROOT / 'tools/window_cache_controller_delivery.py',ROOT / 'tools/1986_raster_bench.c',
        ROOT / 'tools/1986_input_smoke_build.py',ROOT / 'tools/graphics_raster_bench_run.py',
        ROOT / 'tools/vice_capture.py',ROOT / 'src/8502/nmi.s',ROOT / 'src/8502/nmi-common.inc',
        ROOT / 'bench/window-cache-nmi/probe.s',controller.base.OLD / 'probe.cfg',controller.base.OLD / 'gateway.cfg',
        PROOF / 'build/module.bin',PROOF / 'build/gateway.bin',PROOF / 'build/driver.s',
        PROOF / 'build/binding.s',PROOF / 'build/launcher.s']
    paths+=list(extra_inputs)
    linked=['module-envelope.bin','acceptance.inc','validator.bin','gateway.bin','raw.s','binding.s','driver.s','observer.s','probe.c']
    linked += [f'probe-{c}.{ext}' for c in (0,1,'bad-code','bad-header') for ext in ('bin','map')]
    linked += [f'probe-{c}.original.prg' for c in ('bad-code','bad-header')]
    report={'qualification':'standalone trusted acceptance and ticket seam; no GUI hooks or normal link',
        'objects':sizes,'resident_bytes':resident,'available':502,'remaining_before_hooks':502-resident,
        'module_bytes':len(module),'page_calls':pages,'last_page_bytes':last_bytes,
        'negative_controls':controls,'rejection_controls':rejection_controls,
        'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in paths},
        'linked_sha256':{n:digest(WORK / n) for n in linked},
        'program_sha256':{f'probe-{c}.prg':digest(WORK / f'probe-{c}.prg') for c in CASES}}
    (WORK / 'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if not k.endswith('sha256')},indent=2))

def verify(report):
    for key,root in (('source_sha256',ROOT),('linked_sha256',WORK),('program_sha256',WORK)):
        for n,sha in report[key].items():
            if digest(root/n)!=sha:raise ValueError('input drift '+n)

def run(engine,output):
    from graphics_raster_bench_run import emulator_provenance
    report=json.loads((WORK/'build-report.json').read_text());verify(report)
    output.mkdir(parents=True,exist_ok=True)
    if engine=='1986':
        emulator=ROOT.parent/'1986'
        sources=importlib.import_module('1986_input_smoke_build').emulator_sources(emulator)
        provenance=emulator_provenance(emulator,sources)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
        runner=WORK/'1986-acceptance'
        subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator/'src'),
            str(ROOT/'tools/1986_raster_bench.c'),*map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    elif engine=='vice':provenance=subprocess.check_output(['flatpak','info','net.sf.VICE'],text=True)
    else:raise ValueError('run requires --engine')
    decoded={};raw={}
    for case in CASES:
        program=WORK/f'probe-{case}.prg';path=output/f'{engine}-{case}.bin'
        cmd=([str(runner),str(program),str(path),'AVLD'] if engine=='1986' else
            ['python3',str(ROOT/'tools/vice_capture.py'),str(program),str(path),
             '--entry','0x2000','--raw-load','--result-address','0x7fc0',
             '--result-size','8096','--state-offset','5','--timeout','90'])
        subprocess.run(cmd,check=True)
        decoded[str(case)]=(decode(path.read_bytes(),case,report['page_calls']) if isinstance(case,int)
            else negative(path.read_bytes(),case,report['page_calls']))
        raw[path.name]=digest(path);print(json.dumps(decoded[str(case)]),flush=True)
    verify(report)
    if engine=='1986' and emulator_provenance(emulator,sources)!=provenance:raise ValueError('emulator drift')
    (output/f'{engine}-run.json').write_text(json.dumps({'build_report_sha256':digest(WORK/'build-report.json'),
        'program_sha256':report['program_sha256'],
        'raw_sha256':raw,'decoded':decoded,'provenance':provenance},indent=2)+'\n')

def preserve(output):
    report=json.loads((WORK/'build-report.json').read_text());verify(report)
    for engine in ('1986','vice'):
        record=json.loads((output/f'{engine}-run.json').read_text())
        if record['build_report_sha256']!=digest(WORK/'build-report.json'):raise ValueError('run/build mismatch')
        if record['program_sha256']!=report['program_sha256']:raise ValueError('run/program mismatch')
        if set(record['raw_sha256'])!={f'{engine}-{c}.bin' for c in CASES}:raise ValueError('missing run')
        for n,sha in record['raw_sha256'].items():
            if digest(output/n)!=sha:raise ValueError('raw drift')
        for case in CASES:
            data=(output/f'{engine}-{case}.bin').read_bytes()
            value=decode(data,case,report['page_calls']) if isinstance(case,int) else negative(data,case,report['page_calls'])
            if value!=record['decoded'][str(case)]:raise ValueError('decoded drift')
    artifacts=ROOT/'bench/artifacts'/NAME;results=ROOT/'bench/results'/NAME
    if artifacts.exists() or results.exists():raise ValueError('refusing to overwrite evidence')
    artifacts.mkdir(parents=True);results.mkdir(parents=True)
    for n in report['source_sha256']:
        dest=artifacts/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/n,dest)
    for n in set(report['linked_sha256'])|set(report['program_sha256'])|{'build-report.json'}:
        dest=artifacts/'build'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(WORK/n,dest)
    for p in output.iterdir():
        if p.suffix in ('.bin','.json'):shutil.copy2(p,results/p.name)
    for directory in (artifacts,results):
        paths=sorted(p for p in directory.rglob('*') if p.is_file())
        (directory/'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in paths))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('build','run','preserve'))
    p.add_argument('--engine',choices=('1986','vice'))
    p.add_argument('--output',type=Path,default=ROOT / 'build/bench/window-cache-acceptance-results')
    a=p.parse_args()
    if a.action=='build':build()
    elif a.action=='run':run(a.engine,a.output)
    else:preserve(a.output)

if __name__=='__main__':main()

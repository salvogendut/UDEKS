#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute production IPC, syscall dispatch, replies and retirement on sim6502.

MMU registers are simulator RAM; bank switching and native scheduling require
separate emulator qualification. Unrelated services trap if unexpectedly used.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from gen_capability_imports import map_exports
from build_scheduler_overlay import map_segments
ROOT = Path(__file__).resolve().parents[1]

def main():
    out = ROOT/'build/ipc/cpu'; out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').unlink(missing_ok=True)
    def run(*args): subprocess.run(args, cwd=ROOT, check=True)
    def assemble(name, source, *flags):
        obj=out/(name+'.o')
        run('ca65','--cpu','6502','-I','src/8502','-I',str(out),*flags,'-o',str(obj),str(source))
        return str(obj)
    gate=assemble('gate','src/8502/syscall_gate.s','-D','UDEKS_DISK_TIME')
    dump=subprocess.run(['od65','--dump-imports',gate],check=True,text=True,capture_output=True).stdout
    imports=set(re.findall(r'Name:\s*"(_udeks_[^"]+)"',dump))
    supplied={'_udeks_bootfs_finish_ok','_udeks_bootfs_finish_error','_udeks_bootfs_request'}
    (out/'traps.s').write_text('.export __SERVICEBOOT_RUN__ = $93d0, __SERVICEBOOT_SIZE__: absolute = $0000\n.segment "CODE"\ntest_trap: brk\n'+''.join(
        f'.export {name} = test_trap\n' for name in sorted(imports-supplied)))
    (out/'disk-loader-bindings.inc').write_text('STORAGE_CURRENT_TASK = $f110\n'
        '.import _udeks_bootfs_finish_error, _udeks_time_slot_request, _udeks_ipc_request, _udeks_ipc_retire\n'
        'STORAGE_FINISH_ERROR = _udeks_bootfs_finish_error\nTIME_MODULE_REQUEST = _udeks_time_slot_request\n'
        'IPC_REQUEST = _udeks_ipc_request\nIPC_RETIRE = _udeks_ipc_retire\n')
    source=(ROOT/'src/services/filesystem/iec_router.s').read_text()
    (out/'router.s').write_text(source.replace('.segment "CODE"','.segment "ROUTER"'))
    objects=[gate,assemble('ipc','src/kernel/ipc.s'),assemble('traps',out/'traps.s'),
        assemble('router',out/'router.s','-D','UDEKS_DISK_TIME','-D','UDEKS_IPC'),
        assemble('bootfs','src/services/filesystem/bootfs_request.s')]
    parts=[('root',0x8000,0x1000),('router',0xc880,0x80),('vectors',0xcf00,0x100),
           ('hidden',0xd000,0x1000),('bootfs',0xf3ef,0x29b),('common',0xf800,0x109)]
    cfg='MEMORY { Z: start=$06,size=$1a,file="";\n'+''.join(
        f'{name}: start=${base:04x},size=${size:x},file="{out/name}.bin",fill=yes;\n' for name,base,size in parts)+'}\n'
    cfg+='SEGMENTS { ZEROPAGE: load=Z,type=zp; CODE: load=root,type=rw; RODATA: load=root,type=ro; BSS: load=root,type=bss,define=yes; '
    cfg+='ROUTER: load=router,type=rw; SYSCALLS: load=vectors,type=rw; BITMAPCODE: load=hidden,type=rw; '
    cfg+='BITMAPSTATE: load=hidden,type=bss; BOOTFSCODE: load=bootfs,type=rw; TASKREQUEST: load=common,type=rw; }\n'
    (out/'fixture.cfg').write_text(cfg)
    run('cl65','-t','none','-C',str(out/'fixture.cfg'),'-m',str(out/'fixture.map'),
        '-u','_udeks_ipc_state','-u','_udeks_ipc_serial','-o',str(out/'unused.bin'),*objects)
    symbols=map_exports((out/'fixture.map').read_text())
    embed='.segment "RODATA"\n'
    for name,base,size in parts:
        embed+=f'.export _{name}_image\n_{name}_image: .incbin "{out/name}.bin"\n'
    for label,name in [('ipc_state','_udeks_ipc_state'),('ipc_serial','_udeks_ipc_serial')]:
        embed+=f'.export _{label}_address\n_{label}_address: .word ${symbols[name][0]:04x}\n'
    (out/'embed.s').write_text(embed)
    harness=[]
    for name,src in [('check','bench/ipc/check.c'),('call','bench/ipc/call.s'),('embed',str(out/'embed.s'))]:
        obj=str(out/(name+'.o')); run('cl65','-t','sim6502','-Oirs','-c','-o',obj,src); harness.append(obj)
    run('cl65','-t','sim6502','-m',str(out/'check.map'),'-o',str(out/'check.sim65'),*harness)
    if any(end>=0x8000 for name,(_,end,_) in map_segments((out/'check.map').read_text()).items() if name!='ZEROPAGE'):
        raise ValueError('simulator harness reaches production fixture')
    result=subprocess.run(['sim65',str(out/'check.sim65')],cwd=ROOT,capture_output=True,text=True,timeout=120)
    (out/'check.log').write_text(result.stdout+result.stderr); print(result.stdout+result.stderr,end=''); result.check_returncode()
    router=(out/'router.bin').read_bytes()
    address=symbols['_udeks_ipc_retire'][0]
    hook=b'\x20'+address.to_bytes(2,'little')
    if router.count(hook)!=1: raise ValueError('IPC retirement hook changed')
    (out/'router-negative.bin').write_bytes(router.replace(hook,b'\xea'*3))
    (out/'negative-embed.s').write_text(embed.replace(str(out/'router.bin'),str(out/'router-negative.bin')))
    negative=assemble('negative-embed',out/'negative-embed.s')
    run('cl65','-t','sim6502','-o',str(out/'negative.sim65'),*harness[:2],negative)
    failed=subprocess.run(['sim65',str(out/'negative.sim65')],cwd=ROOT,capture_output=True,text=True,timeout=120)
    (out/'negative.log').write_text(failed.stdout+failed.stderr)
    if not failed.returncode or 'FAIL IPC' not in failed.stdout:
        raise AssertionError('missing retirement hook was not detected')
    print('PASS negative control: missing IPC retirement hook detected')
    report={'scope':__doc__,'negative_control':'missing IPC retirement hook detected','images':{n:hashlib.sha256((out/(n+'.bin')).read_bytes()).hexdigest() for n,_,_ in parts}}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__': main()

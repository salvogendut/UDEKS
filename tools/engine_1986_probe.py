#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run engine slice-2 proof against unmodified sibling 1986 and local SDL3."""
import argparse,hashlib,json,os,shlex,shutil,subprocess,tempfile
from pathlib import Path
from importlib import import_module
from gen_capability_imports import map_exports
from build_scheduler_overlay import map_segments
from o65_to_udex import relocate_executable
from task_waitpid_probe import scheduler_symbols
ROOT=Path(__file__).resolve().parents[1]
# Linked worktrees share the root checkout's ROM bundle and sibling emulator.
COMMON=(ROOT/Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=ROOT,text=True).strip())).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--emulator',type=Path,default=COMMON.parent/'1986')
    p.add_argument('--roms',type=Path,default=COMMON/'build/1986-roms')
    p.add_argument('--resume',type=Path);p.add_argument('--timeout',type=int,default=1200)
    args=p.parse_args();emulator=args.emulator.resolve()
    if args.timeout<=0:p.error('positive timeout required')
    out=ROOT/'build/engine/native-1986';out.mkdir(parents=True,exist_ok=True);work=Path(tempfile.mkdtemp(prefix='d81-',dir=out))
    source=ROOT/'build/engine/demo/udeks-engine.d81';disk=work/'test.d81';shutil.copyfile(source,disk)
    sources=import_module('1986_input_smoke_build').emulator_sources(emulator)
    env=os.environ.copy();env['PKG_CONFIG_PATH']=str(emulator/'bin/native-deps/sdl3/lib/pkgconfig')
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],env=env,text=True))
    defines={};images={}
    for app,stem,fields,base,limit in [('client','ENGTEST',('state','error','samples','result'),0x2300,0x3500),('server','ENGINE',('state','error','jobs','handle'),0x8000,0x9000)]:
        symbols=map_exports((ROOT/f'build/engine/{app}/program.map').read_text())
        defines.update({app.upper()+'_'+field.upper():symbols[f'_engine_{app}_{field}'][0]-0x1000 for field in fields})
        images[app]=relocate_executable((ROOT/f'build/engine/{app}/{stem}.BIN').read_bytes(),base,limit-base)[16:]
    kernel=(ROOT/'build/8502/udeks-8502.map').read_text();defines['IPC_STATE']=map_exports(kernel)['_udeks_ipc_state'][0];defines['CONSOLE_BASE']=map_segments(kernel)['LOWBSS'][0]
    defines['DRAW_CELLS']=map_exports((ROOT/'build/user/native-draw/xdraw.map').read_text())['_udeks_xdraw_cells'][0]-0x1000
    (work/'engine_bindings.h').write_text(''.join(f'#define {name} {value}\n' for name,value in defines.items())+''.join('static const unsigned char '+name+'_image[]={'+','.join(str(b) for b in data)+'};\n' for name,data in images.items()))
    h=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=emulator,text=True).strip()
    changes=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=emulator,text=True)
    if changes:raise ValueError('sibling emulator has tracked modifications: '+changes)
    hashes={str(path.relative_to(emulator)):h(path) for path in sorted((emulator/'src').rglob('*')) if path.is_file() and path.suffix in ('.c','.h')}
    runner=work/'smoke';subprocess.run(['cc','-std=gnu11','-O3','-march=native','-mtune=native','-I'+str(emulator/'src'),'-I'+str(work),str(ROOT/'tools/1986_engine_smoke.c'),*map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    provenance={'engine':'sibling native 1986','revision':revision,'source_sha256':hashes,'compiler':subprocess.check_output(['cc','--version'],text=True).splitlines()[0],'flags':'-O3 -march=native -mtune=native','sdl_version':subprocess.check_output(['pkg-config','--modversion','sdl3'],env=env,text=True).strip(),'disk_sha256':h(disk),'harness_sha256':{name:h(ROOT/'tools'/name) for name in ('1986_engine_smoke.c','1986_input_smoke.c','engine_1986_probe.py')},'runner_sha256':h(runner),'rom_sha256':{path.name:h(path) for path in args.roms.glob('*.bin')},'resumed_checkpoint':str(args.resume) if args.resume else None,'physical_c128':False}
    (work/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');print('Native engine work:',work,flush=True)
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    try:
        with (work/'run.log').open('w') as log:
            result=subprocess.run([str(runner),str(args.roms.resolve()),str(disk),str(slots),str(work)]+([str(args.resume.resolve())] if args.resume else []),stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
    except subprocess.TimeoutExpired:
        (work/'incomplete.json').write_text(json.dumps({'qualified':False,'timeout':args.timeout})+'\n');raise SystemExit('Native engine timed out: '+str(work))
    print((work/'run.log').read_text(),end='')
    if result.returncode:raise SystemExit(result.returncode)
    assert h(disk)==h(source)==provenance['disk_sha256']
    assert {name:h(emulator/name) for name in hashes}==hashes
    assert (work/'samples.bin').read_bytes()==bytes((250,0,6,9,14,19,23,25))
    assert (work/'result.bin').read_bytes()==b'\x32\0'
    for name,data in images.items():assert (work/(name+'-code.bin')).read_bytes()==data
    assert (work/'ipc-final.bin').read_bytes()[:2]==b'\0\0'
    (work/'report.json').write_text(json.dumps({'engine':'sibling native 1986','revision':revision,'disk_sha256':h(disk),'checks':['exact max wave','NOP','missing server','acknowledged stop','restart','1351 drawing and clock drag','code/stack guards','cleanup'],'physical_c128':False},indent=2)+'\n')
    print('PASS native engine proof:',work)
if __name__=='__main__':main()

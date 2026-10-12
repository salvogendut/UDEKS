#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned native 1986 raw-IEC IPC qualification; separate from the Flatpak app."""
import argparse,hashlib,json,os,shlex,shutil,subprocess,tempfile
from pathlib import Path
from gen_capability_imports import map_exports
from build_scheduler_overlay import map_segments
from o65_to_udex import relocate_executable
from task_waitpid_probe import scheduler_symbols
from importlib import import_module
ROOT=Path(__file__).resolve().parents[1]
REV='d360c114e33216bf38a086f65af27533f581f6ba'
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--emulator',type=Path,default=ROOT/'build/ipc-1986-source')
    p.add_argument('--sdl-prefix',type=Path,default=ROOT/'build/ipc-sdl3')
    p.add_argument('--roms',type=Path,default=ROOT.parents[1]/'build/1986-roms')
    p.add_argument('--timeout',type=int,default=1200)
    p.add_argument('--resume',type=Path,help='local cold-boot checkpoint, excluded from published evidence')
    p.add_argument('--build-only',action='store_true');args=p.parse_args()
    if args.timeout<=0:p.error('--timeout must be positive')
    out=ROOT/'build/ipc/native-1986';out.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='d81-',dir=out))
    source=ROOT/'build/ipc/demo/udeks-ipc.d81';disk=work/'test.d81';shutil.copyfile(source,disk)
    emulator=args.emulator.resolve();sources=import_module('1986_input_smoke_build').emulator_sources(emulator)
    env=os.environ.copy();env['PKG_CONFIG_PATH']=str(args.sdl_prefix.resolve()/'lib/pkgconfig')
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','--static','sdl3'],text=True,env=env))
    h=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    origin=json.loads((emulator/'.udeks-provenance.json').read_text())
    if origin['revision']!=REV:raise ValueError('expected installed-version emulator source')
    actual={str(path.relative_to(emulator)):h(path) for path in sorted((emulator/'src').rglob('*')) if path.is_file()}
    if actual!=origin['src_sha256']:raise ValueError('emulator source changed from pinned download')
    defines={};images={}
    for app,stem,fields,base,limit in [('client','IPCPING',('state','error','count','reply','peer'),0x2300,0x3500),('server','IPCSRV',('state','error','count','handle'),0x8000,0x9000)]:
        symbols=map_exports((ROOT/f'build/ipc/{app}/program.map').read_text())
        defines.update({app.upper()+'_'+field.upper():symbols[f'_ipc_{app}_{field}'][0]-0x1000 for field in fields})
        images[app]=relocate_executable((ROOT/f'build/ipc/{app}/{stem}.BIN').read_bytes(),base,limit-base)[16:]
    kernel=(ROOT/'build/8502/udeks-8502.map').read_text()
    defines['IPC_STATE']=map_exports(kernel)['_udeks_ipc_state'][0]
    defines['CONSOLE_BASE']=map_segments(kernel)['LOWBSS'][0]
    defines['DRAW_CELLS']=map_exports((ROOT/'build/user/native-draw/xdraw.map').read_text())['_udeks_xdraw_cells'][0]-0x1000
    (work/'ipc_bindings.h').write_text(''.join(f'#define {name} {value}\n' for name,value in defines.items())+''.join('static const unsigned char '+name+'_image[]={'+','.join(str(b) for b in data)+'};\n' for name,data in images.items()))
    runner=work/'smoke'
    subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator/'src'),'-I'+str(work),str(ROOT/'tools/1986_ipc_smoke.c'),*map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    h=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    provenance={'emulator_revision':REV,'emulator_source_sha256':{str(path.relative_to(emulator)):h(path) for path in sorted((emulator/'src').rglob('*')) if path.is_file()},'emulator_archive_sha256':origin['archive_sha256'],'emulator_build_sources':{str(path.relative_to(emulator)):h(path) for path in sources},'emulator_makefile_sha256':h(emulator/'Makefile.am'),'compiler':subprocess.check_output(['cc','--version'],text=True).splitlines()[0],'sdl_library_sha256':h(args.sdl_prefix.resolve()/'lib/libSDL3.a'),'sdl_version':subprocess.check_output(['pkg-config','--modversion','sdl3'],text=True,env=env).strip(),'disk_sha256':h(disk),'runner_sha256':h(runner),'flatpak_qualified':False,'physical_c128':False,'resumed_checkpoint':str(args.resume) if args.resume else None,'harness_sha256':{name:h(ROOT/'tools'/name) for name in ('1986_ipc_smoke.c','1986_input_smoke.c')},'rom_sha256':{path.name:h(path) for path in args.roms.glob('*.bin')}}
    (work/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print('Native 1986 work directory:',work,flush=True)
    if args.build_only:return
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    try:
        with (work/'run.log').open('w') as log:
            result=subprocess.run([str(runner),str(args.roms.resolve()),str(disk),str(slots),str(work)]+([str(args.resume.resolve())] if args.resume else []),stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print((work/'run.log').read_text(),end='')
        (work/'incomplete.json').write_text(json.dumps(dict(status='timeout',timeout_seconds=args.timeout,qualified=False),indent=2)+'\n')
        raise SystemExit('Native 1986 qualification timed out: '+str(work))
    print((work/'run.log').read_text(),end='')
    if result.returncode:raise SystemExit(result.returncode)
    assert 'PASS native 1986 IPC:' in (work/'run.log').read_text()
    assert h(disk)==h(source)==provenance['disk_sha256']
    assert (work/'client-code.bin').read_bytes()==images['client']
    assert (work/'server-code.bin').read_bytes()==images['server']
    assert (work/'ipc-final.bin').read_bytes()[:2]==b'\0\0'
    (work/'report.json').write_text(json.dumps(dict(engine='native 1986',revision=REV,checks=['exact replies','maximum payload','parent client CANCEL','3 restarts','1351 clock drag','1351 drawing','code/stack guards','cleanup'],disk_sha256=h(disk),flatpak_qualified=False,physical_c128=False),indent=2)+'\n')
    print('PASS native 1986 qualification:',work)
if __name__=='__main__':main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build/run the raw-IEC diagnostic without modifying the sibling emulator."""
import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path
import shlex
import shutil
import subprocess
import re
from build_d71 import install_prg_file
from build_d81 import install_file as install_d81_file
from add_disk_apps import add_apps
from gen_capability_imports import map_exports
from storage_public_probe import files

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('input_smoke', ROOT/'tools/1986_input_smoke_build.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--roms', type=Path, required=True)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--drive', choices=('1571','1581'), default='1571',
                        help='explicit ROM-backed drive; D81 requires 1581')
    parser.add_argument('--output', type=Path, default=ROOT/'build/storage/1986')
    parser.add_argument('--disk-exec', action='store_true', help='test disk-only execution fixtures')
    parser.add_argument('--disk-shell', action='store_true', help='require disk-first shell boot and uname')
    parser.add_argument('--sysinfo', action='store_true', help='check startup completion and standalone free/df')
    parser.add_argument('--disk-graphics', action='store_true', help='native managed-app load, window interaction and cancellation')
    parser.add_argument('--drag-regression', action='store_true', help='reported utility/implicit-desktop/repeated-clock-drag sequence')
    parser.add_argument('--boot-mounted', action='store_true', help='drag regression relies on default RC mount, never mounts manually')
    parser.add_argument('--root-namespace', action='store_true', help='system root, cwd, data alias and native window regression')
    parser.add_argument('--xcalc', action='store_true', help='native calculator mouse, arithmetic, console and app-slot checks')
    parser.add_argument('--four-apps', action='store_true', help='four-app native input and independent lifecycle qualification')
    parser.add_argument('--four-native', action='store_true', help='four generic native clients, actual keyboard and 1351 input')
    parser.add_argument('--native-clock', action='store_true', help='two relocatable clocks with native input and legacy peers')
    parser.add_argument('--storage-write', action='store_true', help='public create/readback/reboot with native keyboard and NMI')
    args = parser.parse_args()
    if args.storage_write and any((args.disk_exec,args.disk_shell,args.sysinfo,args.disk_graphics,
                                  args.drag_regression,args.root_namespace,args.xcalc,args.four_apps,
                                  args.four_native,args.native_clock)):
        parser.error('--storage-write is a standalone qualification mode')
    if args.four_native and any((args.disk_exec,args.disk_shell,args.sysinfo,args.disk_graphics,
                                 args.drag_regression,args.root_namespace,args.xcalc,args.four_apps,args.native_clock)):
        parser.error('--four-native is a standalone qualification mode')
    if args.boot_mounted and not args.drag_regression:
        parser.error('--boot-mounted requires --drag-regression')
    if args.native_clock and any((args.disk_exec,args.disk_shell,args.sysinfo,args.disk_graphics,
                                 args.drag_regression,args.root_namespace,args.xcalc,args.four_apps)):
        parser.error('--native-clock is a standalone qualification mode')
    if (args.disk.suffix.lower()=='.d81') != (args.drive=='1581'):
        parser.error('use --drive 1581 with D81, or --drive 1571 with D64/D71')
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if args.storage_write:
        work=Path(tempfile.mkdtemp(prefix='write-',dir=work))
    binary = work/'smoke'
    emulator = args.emulator.resolve()
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'sdl3'], text=True))
    kernel_map = (ROOT/'build/8502/udeks-8502.map').read_text()
    console_base = int(re.search(r'^LOWBSS\s+([0-9A-Fa-f]+)',kernel_map,re.M)[1],16)
    calc_flags = []
    if args.storage_write:
        calc_flags=['-DUDEKS_STORAGE_WRITE_SMOKE','-DUDEKS_DISK_GRAPHICS_SMOKE']
    if args.xcalc or args.four_apps or args.four_native:
        calc_map = (ROOT/('build/user/native-calc/xcalc_native.map' if args.four_native else 'build/user/xcalc.map')).read_text()
        calc_flags = ['-DUDEKS_XCALC_SMOKE','-DUDEKS_DISK_GRAPHICS_SMOKE']
        for symbol, define in (('_udeks_calc_value','VALUE'),('_udeks_calc_error','ERROR')):
            address = re.search(r'\b'+symbol+r'\s+([0-9A-Fa-f]+)\s+RLA',calc_map)[1]
            if args.four_native: address=f'{int(address,16)-0x1000+0x2300:04x}'
            calc_flags.append('-DUDEKS_CALC_'+define+'=0x'+address)
        if (ROOT/'build/user/xcalc.udx').read_bytes()[7]==0:
            calc_flags.append('-DUDEKS_CALC_BANK=0x10000')
    if args.four_native:
        calc_flags.append('-DUDEKS_FOUR_NATIVE_SMOKE')
        wave=map_exports((ROOT/'build/user/native-wave/xwave_native.map').read_text())
        for symbol,define in (('presents','PRESENTS'),('width','WIDTH'),('height','HEIGHT')):
            calc_flags.append('-DUDEKS_WAVE_'+define+'='+str(wave['_native_wave_'+symbol][0]-0x1000+0x18000))
        calc_flags.append('-DUDEKS_WAVE_PROJECTION='+str(wave['_udeks_wave_projection_state'][0]-0x1000+0x18000))
        draw=map_exports((ROOT/'build/user/native-draw/xdraw.map').read_text())
        calc_flags.append('-DUDEKS_DRAW_CELLS='+str(draw['_udeks_xdraw_cells'][0]-0x1000+0x1c600))
    if args.four_apps:
        draw_map=(ROOT/'build/user/xdraw.map').read_text()
        address=re.search(r'\b_udeks_xdraw_cells\s+([0-9A-Fa-f]+)\s+RLA',draw_map)[1]
        calc_flags.extend(['-DUDEKS_FOUR_APPS_SMOKE','-DUDEKS_DRAW_CELLS=0x'+address])
    if args.native_clock:
        clock_map=map_exports((ROOT/'build/native-clients/clock/xclock_native.map').read_text())
        calc_flags=['-DUDEKS_NATIVE_CLOCK_SMOKE','-DUDEKS_DISK_GRAPHICS_SMOKE']
        for name in ('commands','hour','minute','presents','width','height'):
            offset=clock_map['_udeks_native_clock_'+name][0]-0x1000
            calc_flags.append('-DUDEKS_NATIVE_CLOCK_'+name.upper()+'='+str(offset))
    subprocess.run(['cc', '-std=gnu11', '-O2', '-I'+str(emulator/'src'),
                    '-DUDEKS_CONSOLE_BASE='+str(console_base),
                    '-DUDEKS_SMOKE_DRIVE='+args.drive, *calc_flags,
                    *(['-DUDEKS_DISK_EXEC_SMOKE'] if args.disk_exec else []),
                    *(['-DUDEKS_DISK_SHELL_SMOKE'] if args.disk_shell else []),
                    *(['-DUDEKS_SYSINFO_SMOKE'] if args.sysinfo else []),
                    *(['-DUDEKS_DISK_GRAPHICS_SMOKE'] if args.disk_graphics else []),
                    *(['-DUDEKS_DRAG_REGRESSION', '-DUDEKS_DISK_GRAPHICS_SMOKE'] if args.drag_regression else []),
                    *(['-DUDEKS_BOOT_MOUNT_SMOKE'] if args.boot_mounted else []),
                    *(['-DUDEKS_ROOT_NAMESPACE_SMOKE', '-DUDEKS_DRAG_REGRESSION',
                       '-DUDEKS_DISK_GRAPHICS_SMOKE', '-DUDEKS_BOOT_MOUNT_SMOKE'] if args.root_namespace else []),
                    str(ROOT/'tools/1986_storage_smoke.c'),
                    *map(str, smoke.emulator_sources(emulator)), *flags, '-lm', '-o', str(binary)], check=True)
    disk = work/('test'+args.disk.suffix)
    shutil.copyfile(args.disk, disk)
    data = bytearray(disk.read_bytes())
    if args.native_clock:
        program=(ROOT/'build/native-clients/clock/NCLOCK.BIN').read_bytes()
        data=bytearray(add_apps(data,[('NCLOCK.BIN',program),('CLOCK2.BIN',program)]))
    elif not args.disk_exec and not args.storage_write:
        install = install_d81_file if args.drive=='1581' else install_prg_file
        install(data, 'EMPTY', b'', file_type=0x81)
        install(data, 'ONE', b'X', file_type=0x81)
    disk.write_bytes(data)
    if args.storage_write:
        original=bytes(data)
        for phase in ('create','reboot'):
            environment=os.environ.copy()
            environment.pop('UDEKS_WRITE_REBOOT',None)
            if phase=='reboot': environment['UDEKS_WRITE_REBOOT']='1'
            with (work/(phase+'.log')).open('w') as log:
                result=subprocess.run([str(binary),str(args.roms.resolve()),str(disk),
                    smoke.slot_address(ROOT/'build/8502/udeks-scheduler-overlay.map'),str(work/(phase+'.vsf'))],
                    stdout=log,stderr=subprocess.STDOUT,env=environment)
            print((work/(phase+'.log')).read_text())
            if result.returncode: raise SystemExit(result.returncode)
        before,after=files(original),files(disk.read_bytes())
        for name,payload in before.items():
            if after.get(name)!=payload: raise AssertionError(('existing file changed',name))
        expected={n.encode():bytes(i&255 for i in range(size)) for n,size in
                  dict(BINARY=515,ZERO=0,NMITEST=515,GRAPHICS=24).items()}
        if {n:v for n,v in after.items() if n not in before}!=expected:
            raise AssertionError('native persisted file contents disagree')
        (work/'result.json').write_text(json.dumps(dict(drive=args.drive,
            disk_sha256=hashlib.sha256(original).hexdigest(),
            written_disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),
            emulator_revision=subprocess.check_output(['git','-C',str(emulator),'rev-parse','HEAD'],text=True).strip(),
            phases=['create','reboot'],existing_files_unchanged=len(before),
            created={n.decode():len(v) for n,v in expected.items()}),indent=2)+'\n')
        print('PASS native public write evidence:',work)
        return
    with (work/'run.log').open('w') as log:
        result = subprocess.run([str(binary), str(args.roms.resolve()), str(disk),
            smoke.slot_address(ROOT/'build/8502/udeks-scheduler-overlay.map'), str(work/'result.vsf')],
            stdout=log, stderr=subprocess.STDOUT)
    print((work/'run.log').read_text())
    (work/'result.json').write_text(json.dumps({
        'disk_sha256': hashlib.sha256(args.disk.read_bytes()).hexdigest(),
        'test_disk_sha256': hashlib.sha256(disk.read_bytes()).hexdigest(),
        'emulator_revision': subprocess.check_output(
            ['git', '-C', str(emulator), 'rev-parse', 'HEAD'], text=True).strip(),
        'exit_status': result.returncode, 'raw_iec': True, 'disk_exec': args.disk_exec,
        'disk_shell': args.disk_shell, 'sysinfo': args.sysinfo, 'disk_graphics': args.disk_graphics,
        'drag_regression': args.drag_regression,
        'boot_mounted': args.boot_mounted,
        'root_namespace': args.root_namespace,
        'xcalc': args.xcalc,
        'four_apps': args.four_apps,
        'four_native': args.four_native,
        'native_clock': args.native_clock,
        'drive': int(args.drive),
        **({'program_sha256':hashlib.sha256(program).hexdigest()} if args.native_clock else {}),
    }, indent=2)+'\n')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()

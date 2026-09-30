#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build/run the raw-IEC diagnostic without modifying the sibling emulator."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import re
from build_d71 import install_prg_file

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('input_smoke', ROOT/'tools/1986_input_smoke_build.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--roms', type=Path, required=True)
    parser.add_argument('--disk', type=Path, default=ROOT/'build/boot/udeks.d64')
    parser.add_argument('--output', type=Path, default=ROOT/'build/storage/1986')
    parser.add_argument('--disk-exec', action='store_true', help='test disk-only execution fixtures')
    parser.add_argument('--disk-shell', action='store_true', help='require disk-first shell boot and uname')
    parser.add_argument('--sysinfo', action='store_true', help='check startup completion and standalone free/df')
    parser.add_argument('--disk-graphics', action='store_true', help='native managed-app load, window interaction and cancellation')
    parser.add_argument('--drag-regression', action='store_true', help='reported utility/implicit-desktop/repeated-clock-drag sequence')
    parser.add_argument('--boot-mounted', action='store_true', help='drag regression relies on default RC mount, never mounts manually')
    parser.add_argument('--root-namespace', action='store_true', help='system root, cwd, data alias and native window regression')
    parser.add_argument('--xcalc', action='store_true', help='native calculator mouse, arithmetic, console and app-slot checks')
    args = parser.parse_args()
    if args.boot_mounted and not args.drag_regression:
        parser.error('--boot-mounted requires --drag-regression')
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    binary = work/'smoke'
    emulator = args.emulator.resolve()
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'sdl3'], text=True))
    kernel_map = (ROOT/'build/8502/udeks-8502.map').read_text()
    console_base = int(re.search(r'^LOWBSS\s+([0-9A-Fa-f]+)',kernel_map,re.M)[1],16)
    calc_flags = []
    if args.xcalc:
        calc_map = (ROOT/'build/user/xcalc.map').read_text()
        calc_flags = ['-DUDEKS_XCALC_SMOKE','-DUDEKS_DISK_GRAPHICS_SMOKE']
        for symbol, define in (('_udeks_calc_value','VALUE'),('_udeks_calc_error','ERROR')):
            address = re.search(r'\b'+symbol+r'\s+([0-9A-Fa-f]+)\s+RLA',calc_map)[1]
            calc_flags.append('-DUDEKS_CALC_'+define+'=0x'+address)
    subprocess.run(['cc', '-std=gnu11', '-O2', '-I'+str(emulator/'src'),
                    '-DUDEKS_CONSOLE_BASE='+str(console_base), *calc_flags,
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
    if not args.disk_exec:
        install_prg_file(data, 'EMPTY', b'', file_type=0x81)
        install_prg_file(data, 'ONE', b'X', file_type=0x81)
    disk.write_bytes(data)
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
    }, indent=2)+'\n')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()

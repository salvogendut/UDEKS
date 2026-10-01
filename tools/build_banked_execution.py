#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build two independently linked C clients in the reference container."""
import subprocess
from pathlib import Path
from build_scheduler_overlay import map_segments
from build_udex import build_executable
from gen_capability_imports import map_exports

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'build/four-apps/native'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    template = (ROOT/'cfg/8502-banked-client.cfg.in').read_text()
    def run(*args): subprocess.run(args, cwd=ROOT, check=True)
    run('ca65','--cpu','6502','-o',str(OUT/'entry.o'),'user/probes/banked_client_entry.s')
    for tag, base, size in ((3,0x2300,0x1200),(4,0x3500,0xB00)):
        name = 'native'+str(tag)
        config = OUT/(name+'.cfg')
        config.write_text(template.replace('@BASE@',f'${base:04x}').replace('@SIZE@',f'${size:04x}'))
        run('cc65','-t','none','--cpu','6502','--standard','c99','-Oirs',
            '-D','CLIENT_TAG='+str(tag),'-o',str(OUT/(name+'.s')),'user/probes/banked_client.c')
        run('ca65','--cpu','6502','-o',str(OUT/(name+'.o')),str(OUT/(name+'.s')))
        exports = ('_udeks_program_entry','_probe_ready','_probe_progress','_probe_control',
                   '_probe_error','_probe_low_sp','_probe_value')
        flags = [item for name in exports for item in ('-u',name)]
        run('cl65','-t','none','--cpu','6502','-C',str(config),'-m',str(OUT/(name+'.map')),
            *flags,'-o',str(OUT/(name+'.bin')),str(OUT/'entry.o'),str(OUT/(name+'.o')))
        map_text = (OUT/(name+'.map')).read_text()
        bss = map_segments(map_text)['BSS'][2]
        entry = map_exports(map_text)['_udeks_program_entry'][0]
        image = (OUT/(name+'.bin')).read_bytes()
        if len(image)+16 > size or len(image)+bss > size or entry != base+2:
            raise ValueError('native fixture exceeds its placement/entry contract')
        (OUT/(name+'.udx')).write_bytes(build_executable(image, cpu=1,
            load_address=base, entry_address=entry, bss_size=bss, flags=0))
        print(name, len(image), 'image bytes,', bss, 'BSS bytes')


if __name__ == '__main__': main()

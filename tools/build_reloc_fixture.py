#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build once to o65, prove relocation equals independent flat links at both bases."""
import json
import subprocess
from pathlib import Path
from o65_to_udex import pack_o65, relocate_executable
from gen_capability_imports import map_exports
from build_scheduler_overlay import map_segments
from build_udex import build_executable

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/generic-apps'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    def run(*args): subprocess.run(args,cwd=ROOT,check=True)
    run('cc65','-t','none','--cpu','6502','--standard','c99','-Oirs',
        '-D','CLIENT_TAG=3','-D','PROBE_RELOCATION=1','-o',str(OUT/'probe.s'),
        'user/probes/banked_client.c')
    objects=[]
    for name,source in (('entry','user/probes/banked_client_entry.s'),
                        ('probe',str(OUT/'probe.s')),('split','user/probes/reloc_split.s')):
        target=str(OUT/(name+'.o'));objects.append(target)
        run('ca65','--cpu','6502','-o',target,source)
    exports=('_udeks_program_entry','_probe_ready','_probe_control','_probe_progress',
        '_probe_error','_probe_low_sp','_probe_value')
    flags=[item for name in exports for item in ('-u',name)]
    run('cl65','-t','none','--cpu','6502','-C','cfg/8502-reloc-app.cfg',
        '-m',str(OUT/'probe.map'),*flags,'-o',str(OUT/'probe.o65'),*objects)
    entry=map_exports((OUT/'probe.map').read_text())['_udeks_program_entry'][0]
    executable=pack_o65((OUT/'probe.o65').read_bytes(),entry)
    (OUT/'relocapp.udx').write_bytes(executable)
    # Independent flat links are test oracles only, never distributed variants.
    template=(ROOT/'cfg/8502-banked-client.cfg.in').read_text()
    results=[]
    for base,size in ((0x2300,0x1200),(0x3500,0xb00)):
        name=f'oracle-{base:04x}'
        config=OUT/(name+'.cfg')
        config.write_text(template.replace('@BASE@',f'${base:04x}').replace('@SIZE@',f'${size:04x}'))
        run('cl65','-t','none','--cpu','6502','-C',str(config),'-m',str(OUT/(name+'.map')),
            *flags,'-o',str(OUT/(name+'.bin')),*objects)
        text=(OUT/(name+'.map')).read_text()
        fixed=build_executable((OUT/(name+'.bin')).read_bytes(),cpu=1,load_address=base,
            entry_address=map_exports(text)['_udeks_program_entry'][0],
            bss_size=map_segments(text)['BSS'][2],flags=0)
        relocated=relocate_executable(executable,base,size)
        if fixed!=relocated: raise ValueError(f'relocation differs from flat-link oracle at {base:04x}')
        (OUT/(name+'.udx')).write_bytes(fixed)
        results.append(dict(base=base,capacity=size,flat_link_matches=True))
    (OUT/'build-result.json').write_text(json.dumps(dict(file_size=len(executable),
        image_size=int.from_bytes(executable[10:12],'little'),
        bss_size=int.from_bytes(executable[12:14],'little'),destinations=results),indent=2)+'\n')
    print('One relocatable binary matches both independently linked C images:',len(executable),'bytes')


if __name__=='__main__':main()

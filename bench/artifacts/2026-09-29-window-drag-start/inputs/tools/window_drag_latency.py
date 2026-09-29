#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only native mouse drag-start timing on preserved candidate disks."""
import argparse
import importlib
import json
import os
import shlex
import subprocess
from pathlib import Path
from window_cache_manager import replace
from graphics_raster_bench_run import emulator_provenance

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/drag-start-latency'
VARIANTS={'occlusion':('2026-09-28-window-cache-occlusion','window-cache-occlusion'),
          'partial':('2026-09-29-window-cache-partial-manager','window-cache-partial'),
          'deferred':(None,'window-drag-start')}


def instrument(source):
    source=replace(source,'''    joyports_mouse_button(&machine->joyports,0,false,true);
    for(unsigned n=0;n<10000 && (!byte(0xF248)||word(0xF258)==before);++n)frames(1);''', '''    unsigned start=c128_frame_count,phase=byte(CACHE_PHASE);
    joyports_mouse_button(&machine->joyports,0,false,true);
    for(unsigned n=0;n<10000 && (!byte(0xF248)||word(0xF258)==before);++n)frames(1);
    printf("drag start: resize=%u phase=%u frames=%u x=%u y=%u\\n",
        resize,phase,(unsigned)c128_frame_count-start,wave_x(),wave_y());fflush(stdout);''')
    source=replace(source,'    command("xwave");\n', '''    /* Also measure the clock while it is the only window. */
    pointer_to(144,107);
    unsigned clock_before=word(0xF258),clock_start=c128_frame_count;
    joyports_mouse_button(&machine->joyports,0,false,true);
    for(unsigned n=0;n<10000 && (!byte(0xF248)||word(0xF258)==clock_before);++n)frames(1);
    require(byte(0xF248)&&word(0xF258)==((clock_before+1)&65535),"clock drag did not begin");
    printf("clock drag start: frames=%u\\n",(unsigned)c128_frame_count-clock_start);
    unsigned clock_finish=word(0xF25A);drag_release(clock_finish);
    frames(300);require(byte(CACHE_PHASE)==0,"clock-only drag retained a cache");
    command("xwave");
''')
    source=replace(source,'    /* Partial paste + Ctrl+C must cancel, without stranding the console. */', '''    /* Place the wave below the clock title, then drag the clock while a
     * completed wave is underneath. This is the user's reported case. */
    before=drag_begin(0);pointer_to(144+20,88+46);drag_release(before);ready();pixel_oracle();
    pointer_to(144,107);clock_before=word(0xF258);clock_start=c128_frame_count;
    joyports_mouse_button(&machine->joyports,0,false,true);
    for(unsigned n=0;n<10000 && (!byte(0xF248)||word(0xF258)==clock_before);++n)frames(1);
    require(byte(0xF248)==1 && word(0xF258)==((clock_before+1)&65535),"overlap clock drag did not begin");
    printf("overlap clock drag start: frames=%u\\n",(unsigned)c128_frame_count-clock_start);
    unsigned outline_moves=word(0xF256);
    pointer_to(156,114);frames(40);
    require(word(0xF256)>outline_moves,"clock outline did not track native mouse");
    clock_finish=word(0xF25A);drag_release(clock_finish);frames(300);
    require(word(0xF26C)==21,"clock drag unexpectedly acquired the Z80");
    require(memcmp(machine->mem.ram+0xA1E0,machine->mem.ram+0x16000,8000)==0,
        "clock drag left shadow/VIC disagreement");
    /* xwave is still the foreground command: stop it before testing typing. */
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,false);
    wait_byte(0xF265,2,"foreground wave did not cancel after clock drag");idle();
    command("echo clock drag alive");idle();command("xinit -q");idle();
    puts("PASS: native clock-only/overlap drag-start timing and shutdown");
    return; /* Diagnostic scope, not another full compositor qualification. */
    /* Partial paste + Ctrl+C must cancel, without stranding the console. */''')
    return source


def run(variant):
    import hashlib
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    name,private=VARIANTS[variant]
    if name is None:
        import window_drag_start as fix
        fix.configure();fix.live.verify_build()
        archive=fix.live.WORK
        native_path=archive/'native.c'
        disk_paths={fmt:archive/f'udeks-cache.{fmt}' for fmt in ('d71','d64')}
        map_path=fix.live.REPO/'build/8502/udeks-scheduler-overlay.map'
        bindings=(archive/'report.json',native_path,*disk_paths.values())
    else:
        archive=ROOT/'bench/artifacts'/name
        for line in (archive/'SHA256SUMS').read_text().splitlines():
            value,path=line.split('  ',1)
            if sha(archive/path)!=value:raise ValueError('archive drift '+path)
        native_path=archive/'build/native.c'
        disk_paths={fmt:archive/f'build/udeks-cache.{fmt}' for fmt in ('d71','d64')}
        map_path=archive/'inputs/build'/private/'repo/build/8502/udeks-scheduler-overlay.map'
        bindings=(archive/'SHA256SUMS',native_path,*disk_paths.values())
    work=WORK/variant;work.mkdir(parents=True,exist_ok=True)
    source=work/'native.c';source.write_text(instrument(native_path.read_text()))
    if variant=='deferred':
        source.write_text(replace(source.read_text(),
            '    printf("overlap clock drag start: frames=%u\\n",(unsigned)c128_frame_count-clock_start);',
            '''    require((unsigned)c128_frame_count-clock_start <= 30,"overlap clock drag-start exceeded 30 frames");
    printf("overlap clock drag start: frames=%u\\n",(unsigned)c128_frame_count-clock_start);'''))
    emulator=ROOT.parent/'1986'
    builder=importlib.import_module('1986_input_smoke_build')
    sources=builder.emulator_sources(emulator)
    provenance=emulator_provenance(emulator,sources)
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
    runner=work/'native'
    subprocess.run(['cc','-std=gnu11','-O2','-I'+str(emulator/'src'),str(source),
        *map(str,sources),*flags,'-lm','-o',str(runner)],check=True)
    slot=builder.slot_address(map_path)
    env=os.environ.copy();env.update(UDEKS_DRAG_STRESS='16',UDEKS_DRAG_CLOCK='1')
    for fmt in ('d71','d64'):
        result=subprocess.run([str(runner),str(emulator/'roms'),
            str(disk_paths[fmt]),slot,str(work/(fmt+'.vsf'))],
            env=env,text=True,capture_output=True)
        (work/(fmt+'.log')).write_text(result.stdout+result.stderr)
        print(result.stdout+result.stderr,flush=True)
        if result.returncode:raise ValueError('latency probe failed')
    if emulator_provenance(emulator,sources)!=provenance:raise ValueError('emulator changed')
    (work/'run.json').write_text(json.dumps({'provenance':provenance,
        'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in
            (Path(__file__),*bindings)},
        'source_sha256':sha(source),'runner_sha256':sha(runner),
        'log_sha256':{fmt:sha(work/(fmt+'.log')) for fmt in ('d71','d64')}},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant',choices=tuple(VARIANTS))
    run(p.parse_args().variant)

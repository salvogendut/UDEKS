#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify visible-strip background repair on isolated tiled-cache disks."""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

import window_cache_live as live
from window_cache_manager import BASE, replace
from window_cache_repaint import tiled, profile, measurements

ROOT = live.ROOT
WORK = ROOT / 'build/window-cache-occlusion'
NAME = '2026-09-28-window-cache-occlusion'


def occluded(source):
    text = tiled(source)
    # Keep the chrome's repeatedly accessed window pointer in cc65's register
    # bank. This changes storage, not drawing order or the public ABI.
    text = replace(text, 'static void draw_chrome(const struct udeks_window *window)',
                   'static void draw_chrome(register const struct udeks_window *window)')
    text = replace(text, 'static void draw_title(const struct udeks_window *window)',
                   'static void draw_title(register const struct udeks_window *window)')
    text = text.replace('const struct udeks_window *window)',
                        'register const struct udeks_window *window)')
    text = text.replace('register register ', 'register ')
    text = replace(text, '''static void cache_paint_image(unsigned char handle)
{
''', '''static void cache_paint_image(unsigned char handle)
{
    register struct udeks_window *cached = window_by_handle(handle);
    unsigned char paste = set_damage_intersection(
        cached->x, cached->y, cached->width, cached->height);
''')
    text = replace(text, '''    if (cache_request(handle, UDEKS_CACHE_COMMAND_PASTE) != UDEKS_CACHE_OK)
        compose_damage(UDEKS_WINDOW_NONE);''', '''    if (paste == 0) cache_phase = UDEKS_CACHE_READY;
    else if (cache_request(handle, UDEKS_CACHE_COMMAND_PASTE) != UDEKS_CACHE_OK)
        compose_damage(UDEKS_WINDOW_NONE);''')
    return replace(text, '''        damage_add(window_by_handle(cache_owner));
        cache_paint_image(cache_owner);''', '''        window = window_by_handle(cache_owner);
        /* A top retained image can hide all of a lower damage rectangle,
         * or leave just its upper strip. Repair that strip without touching
         * the retained pixels. Complex intersections keep the paste path. */
        if (damage_left >= window->x &&
            damage_right <= window->x + window->width &&
            damage_bottom <= window->y + window->height) {
            cache_phase = 0x82u; /* Frontend repair busy; banked image READY. */
            if (damage_bottom > window->y) damage_bottom = window->y;
            if (damage_top < damage_bottom) {
                drag_mode = CACHED_MOVE;
                compose_damage(cache_owner);
                drag_mode = 0;
            }
            /* An entirely hidden client still acknowledges its update.
             * A zero clip makes its callback drawing harmless and prevents
             * repeated requests (e.g. every clock poll after a minute tick). */
            window = window_by_handle(handle);
            if (window->paint != 0 &&
                damage_bottom <= damage_top + UDEKS_WINDOW_TITLE_HEIGHT + 1u) {
                window->flags &= (unsigned char)~IMAGE_COMPLETE;
                udeks_vic_bitmap_set_clip(0, 0, 0, 0);
                window->paint(handle);
                udeks_vic_bitmap_reset_clip();
            }
            cache_phase = UDEKS_CACHE_READY;
        } else cache_paint_image(cache_owner);''')


def configure(reference=False):
    global WORK, NAME
    WORK = ROOT / ('build/window-cache-occlusion-reference' if reference else 'build/window-cache-occlusion')
    NAME = '2026-09-28-window-cache-occlusion'+('-reference' if reference else '')
    live.WORK = WORK
    live.REPO = WORK / 'repo'
    live.NAME = NAME
    live.candidate = tiled if reference else occluded


def native_profile(code):
    from gen_capability_imports import map_exports
    symbols = map_exports((live.REPO / 'build/8502/udeks-8502.map').read_text())
    code = profile(code)
    code = replace(code, "        else if (*value == ' ') key(SDL_SCANCODE_SPACE);", """        else if (*value >= '1' && *value <= '9') key(SDL_SCANCODE_1 + *value - '1');
        else if (*value == '0') key(SDL_SCANCODE_0);
        else if (*value == ' ') key(SDL_SCANCODE_SPACE);""")
    code = replace(code, 'static unsigned profile_stage, profile_pages[3][32], profile_calls[3];',
        '''static unsigned profile_stage, profile_pages[3][32], profile_calls[3];
static unsigned entry_sp,entry_a,entry_x,entry_y,entry_p,entry_retries;''')
    code = replace(code, '        if(profile_return_id || machine->cpu.a>=32) {', '''        /* A breakpoint precedes interrupt dispatch. An IRQ/NMI can run
         * instead of the first opcode and RTI to this same entry. Count the
         * call once, require the identical registers and caller frame, and
         * leave the interrupt's cycles in the elapsed measurement. */
        unsigned current_return=1+c128_debug_mem_read(machine,cpu,0x100|((machine->cpu.sp+1)&255))+
            (c128_debug_mem_read(machine,cpu,0x100|((machine->cpu.sp+2)&255))<<8);
        if(profile_return_id && machine->cpu.sp==entry_sp && machine->cpu.a==entry_a &&
           machine->cpu.x==entry_x && machine->cpu.y==entry_y && machine->cpu.p==entry_p &&
           current_return==profile_return_pc) {
            ++entry_retries;c128_debug_continue(machine);return;
        }
        if(profile_return_id || machine->cpu.a>=32) {''')
    code = replace(code, '        ++profile_pages[profile_stage][machine->cpu.a];', '''        entry_sp=machine->cpu.sp;entry_a=machine->cpu.a;entry_x=machine->cpu.x;
        entry_y=machine->cpu.y;entry_p=machine->cpu.p;
        ++profile_pages[profile_stage][machine->cpu.a];''')
    code = replace(code, 'static unsigned profile_clock_before;', f'''static unsigned profile_clock_before;
/* Published/link-asserted syscall entry, not an unexported implementation PC. */
#define CLOCK_SET 0xcf40u
#define CLOCK_CACHE_PHASE 0x{symbols['_cache_phase'][0]:04x}u
static unsigned clock_armed,clock_started,clock_done,clock_minute,clock_start,clock_finish;
static unsigned clock_copies,clock_callbacks;
static unsigned clock_entry_id;''')
    code = replace(code, '    if(pc==PROFILE_DISABLE) {', '''    if(pc==CLOCK_SET && clock_armed) {
        if(!clock_started) {
            clock_started=1;clock_start=c128_frame_count;
            memset(profile_pages,0,sizeof(profile_pages));memset(profile_calls,0,sizeof(profile_calls));
            memset(profile_cycles,0,sizeof(profile_cycles));profile_stage=2;
            profile_clock_before=word(0xF230);
        }
    } else if(pc==PROFILE_DISABLE) {''')
    code = replace(code, '        } while((unsigned)c128_frame_count==before);', '''        } while((unsigned)c128_frame_count==before);
        if(clock_started && !clock_done && byte(0xF22C)==12 && byte(0xF22D)==clock_minute &&
           byte(CLOCK_CACHE_PHASE)==2) {
            /* READY is the lease state; the final batch's commit can still
             * be in flight. Require the fixed dirty-page map to drain and
             * the measured page call to return before declaring visible. */
            unsigned dirty=profile_return_id!=0;
            for(unsigned page=0;page<32;++page)dirty|=byte(0xE190+page);
            if(!dirty) {
                clock_done=1;clock_finish=c128_frame_count;clock_copies=profile_calls[2];
                clock_callbacks=(word(0xF230)-profile_clock_before)&65535;profile_stage=0;
            }
        }''')
    code = replace(code, 'static void drag_stress(unsigned count) {', '''static void clock_repairs(void) {
    const unsigned xs[3]={109,109,144},ys[3]={40,65,88};
    unsigned paints=word(0xF270),jobs=word(0xF26C);
    clock_entry_id=c128_debug_breakpoint_add(machine,C128_DEBUG_CPU_8502,CLOCK_SET);
    require(clock_entry_id!=0,"no clock-set breakpoint");
    for(unsigned i=0;i<3;++i) {
        unsigned before=drag_begin(0);pointer_to(xs[i]+20,ys[i]+46);
        /* pointer_to allows one pixel, appropriate for general mouse input.
         * Here use real relative mouse motion to settle an exact geometry
         * before release so both timing variants see the identical strip. */
        for(unsigned n=0;n<500;++n) {
            int dx=(int)xs[i]-(int)word(0xF249),dy=(int)ys[i]-(int)byte(0xF24B);
            if(!dx && !dy) {frames(8);if(word(0xF249)==xs[i] && byte(0xF24B)==ys[i])break;}
            else {if(dx>8)dx=8;if(dx< -8)dx=-8;if(dy>8)dy=8;if(dy< -8)dy=-8;
                joyports_mouse_motion(&machine->joyports,0,dx,dy);frames(8);}
            require(n!=499,"exact native drag did not settle");
        }
        drag_release(before);
        ready();pixel_oracle();require(wave_x()==xs[i] && wave_y()==ys[i],"clock case geometry");
        clock_armed=1;clock_started=clock_done=0;clock_minute=10+i;
        char text[32];snprintf(text,sizeof(text),"date 12%02u00",clock_minute);command(text);idle();
        for(unsigned n=0;n<10000 && !clock_done;++n)frames(1);
        require(clock_started && clock_done,"native date did not repaint clock");
        require(clock_callbacks==1,"clock update callback was repeated or omitted");
        unsigned callbacks=word(0xF230);frames(120);ready();pixel_oracle();
        require(word(0xF230)==callbacks,"hidden clock repeatedly requested a repair");
        require(word(0xF270)==paints && word(0xF26C)==jobs,"clock update repainted/recomputed wave");
        require(memcmp(machine->mem.ram+0xA1E0,machine->mem.ram+0x16000,8000)==0,
            "clock repair left VIC/shadow disagreement");
        for(unsigned surface=0;surface<2;++surface) {
            char filename[4096];snprintf(filename,sizeof(filename),"%.*s-clock-%u-%s.bin",
                (int)strlen(snapshot_path)-4,snapshot_path,i,surface?"bitmap":"shadow");
            FILE *file=fopen(filename,"wb");require(file!=NULL,"open clock pixel evidence");
            require(fwrite(machine->mem.ram+(surface?0x16000:0xA1E0),1,8000,file)==8000,
                "write clock pixel evidence");fclose(file);
        }
        printf("clock repair %u: x=%u y=%u frames=%u pages=%u callbacks=%u pixels=OK\\n",
            i,wave_x(),wave_y(),clock_finish-clock_start,clock_copies,clock_callbacks);
        clock_armed=clock_started=0;
    }
    c128_debug_breakpoint_remove(machine,clock_entry_id);
    printf("profiler entry redispatches: %u\\n",entry_retries);
}
static void drag_stress(unsigned count) {''')
    return replace(code, '    /* Enlarged image must use redraw fallback, not overrun the cache lease. */',
        '    clock_repairs();\n    /* Enlarged image must use redraw fallback, not overrun the cache lease. */')


def compare():
    values = {}
    inputs = {}
    raw_bindings = {}
    for reference in (True, False):
        configure(reference)
        live.verify_build()
        binding = json.loads((WORK / '1986-run.json').read_text())
        if binding['report_sha256'] != live.digest(WORK / 'report.json'):
            raise ValueError('stale native qualification')
        raw_bindings[WORK.name] = binding['raw_sha256']
        for fmt in ('d71', 'd64'):
            path = WORK / f'1986-{fmt}.log'
            if live.digest(path) != binding['results'][fmt]['log_sha256']:
                raise ValueError('native log drift')
            values.setdefault(fmt, {})['reference' if reference else 'occlusion'] = measurements(path.read_text())
            values[fmt]['reference' if reference else 'occlusion']['clock_repairs'] = clock_measurements(path.read_text())
        for path in (WORK / 'report.json', WORK / '1986-run.json',
                     WORK / '1986-d71.log', WORK / '1986-d64.log'):
            inputs[str(path.relative_to(ROOT))] = live.digest(path)
    for fmt, pair in values.items():
        before, after = pair['reference'], pair['occlusion']
        if [(m['x'], m['y']) for m in before['moves']] != [(m['x'], m['y']) for m in after['moves']]:
            raise ValueError('move geometry mismatch')
        for old, new in zip(before['clock_repairs'][:2], after['clock_repairs'][:2]):
            if new['frames'] >= old['frames'] or new['pages'] >= old['pages']:
                raise ValueError('no measured hidden/strip clock improvement')
        for case in range(3):
            pixels = []
            for variant in ('window-cache-occlusion-reference', 'window-cache-occlusion'):
                for surface in ('shadow', 'bitmap'):
                    path = ROOT / 'build' / variant / f'1986-{fmt}-clock-{case}-{surface}.bin'
                    if live.digest(path) != raw_bindings[variant].get(path.name):
                        raise ValueError('clock pixel evidence not bound to native run')
                    pixels.append(path.read_bytes())
                    inputs[str(path.relative_to(ROOT))] = live.digest(path)
            if len(pixels[0]) != 8000 or any(image != pixels[0] for image in pixels):
                raise ValueError('complete clock-case canvas mismatch')
    result = {'scope': 'native 1986 mouse/keyboard; same geometry, clock and NMI stimulus',
              'inputs_sha256': inputs, 'values': values}
    (WORK / 'comparison.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({fmt: {variant: {k: v for k, v in row.items()
        if k.startswith('median_') or k in ('worst_paste_frames', 'cancel_frames', 'clock_repairs')}
        for variant, row in pair.items()} for fmt, pair in values.items()}, indent=2))


def clock_measurements(log):
    rows = [dict(zip(('case', 'x', 'y', 'frames', 'pages', 'callbacks'), map(int, match)))
            for match in re.findall(r'^clock repair (\d+): x=(\d+) y=(\d+) frames=(\d+) pages=(\d+) callbacks=(\d+) pixels=OK$', log, re.M)]
    if [(v['case'], v['x'], v['y'], v['callbacks']) for v in rows] != [
            (0, 109, 40, 1), (1, 109, 65, 1), (2, 144, 88, 1)] or any(v['frames'] == 0 for v in rows):
        raise ValueError('incomplete/duplicate clock repair qualification')
    return rows


def preserve():
    comparison = ROOT / 'build/window-cache-occlusion/comparison.json'
    data = json.loads(comparison.read_text())
    for name, sha in data['inputs_sha256'].items():
        if live.digest(ROOT / name) != sha:
            raise ValueError('comparison binding drift')
    live.preserve()
    result = ROOT / 'bench/results' / NAME
    shutil.copy2(comparison, result / 'comparison.json')
    paths = sorted(p for p in result.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    (result / 'SHA256SUMS').write_text(''.join(f'{live.digest(p)}  {p.relative_to(result)}\n' for p in paths))


def sizes():
    from graphics_span_bench import object_sizes
    WORK.mkdir(parents=True, exist_ok=True)
    text = occluded(BASE.read_text())
    variants = {'current': text}
    for declaration in ('unsigned char index;', 'unsigned char rank;',
                        'unsigned int left;', 'unsigned int right;',
                        'unsigned char top;', 'unsigned char bottom;',
                        'unsigned char row;', 'unsigned char column;'):
        variants[declaration.split()[-1][:-1]] = text.replace(declaration, 'register '+declaration)
    variants['all'] = text
    for declaration in ('unsigned char index;', 'unsigned char rank;', 'unsigned char row;', 'unsigned char column;'):
        variants['all'] = variants['all'].replace(declaration, 'register '+declaration)
    for name, source in variants.items():
        path = WORK / ('size-'+name+'.c')
        path.write_text(source)
        subprocess.run(['cl65', '-t', 'none', '--cpu', '6502', '--standard', 'c99', '-Oirs',
            '-I', str(ROOT / 'include'), '-c', '-o', str(path.with_suffix('.o')), str(path)], check=True)
        print(name, object_sizes(path.with_suffix('.o'))['CODE'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', action='store_true', help='unaltered tiled compositor; identical clock probe')
    parser.add_argument('action', choices=('build', '1986', 'vice', 'compare', 'preserve', 'sizes'))
    args = parser.parse_args()
    configure(args.reference)
    if args.action == 'build':
        live.build((Path(__file__), ROOT / 'tools/window_cache_repaint.py',
                    ROOT / 'bench/window-cache-manager/profile.inc',
                    ROOT / 'bench/window-cache-manager/occlusion-host.inc',
                    ROOT / 'tests/test_window_cache_occlusion.py'))
    elif args.action == '1986':
        live.probe_native(native_profile)
    elif args.action == 'sizes':
        sizes()
    else:
        {'vice': live.probe_vice, 'compare': compare, 'preserve': preserve}[args.action]()

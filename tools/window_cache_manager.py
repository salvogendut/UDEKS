#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate and measure the private cache compositor candidate; no OS writes."""
import argparse
import json
import subprocess
from pathlib import Path
from graphics_span_bench import object_sizes

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/window-cache-manager'
BASE = ROOT / 'src/services/window/window_manager.c'
ADAPTER = ROOT / 'bench/window-cache-manager/adapter.inc'


def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError('compositor seam changed: '+old[:80])
    return source.replace(old, new)


def registered(source):
    return source.replace('    struct udeks_window *window;',
                          '    register struct udeks_window *window;')


def candidate(source):
    source = registered(source)
    source = replace(source, 'static unsigned char paint_window_damage(unsigned char handle);',
        ADAPTER.read_text()+'\nstatic unsigned char paint_window_damage(unsigned char handle);')
    source = replace(source, '    return dragging_handle != UDEKS_WINDOW_NONE;\n',
        '    return dragging_handle != UDEKS_WINDOW_NONE ||\n'
        '        cache_phase == UDEKS_CACHE_CAPTURING || cache_phase == UDEKS_CACHE_PASTING;\n')
    source = replace(source, '    window->flags &= (unsigned char)~IMAGE_COMPLETE;\n    udeks_vic_bitmap_set_clip(',
        '''    cache_invalidate();
    window->flags &= (unsigned char)~IMAGE_COMPLETE;
    udeks_vic_bitmap_set_clip(''')
    source = replace(source, '    window->flags |= IMAGE_COMPLETE;\n    return UDEKS_WINDOW_OK;',
        '''    window->flags |= IMAGE_COMPLETE;
    if (cache_accept_state == 0x80u && cache_phase == UDEKS_CACHE_EMPTY)
        cache_request(handle, UDEKS_CACHE_COMMAND_CAPTURE);
    return UDEKS_WINDOW_OK;''')
    source = replace(source, '    udeks_vic_pointer_busy_begin(UDEKS_VIC_BUSY_REPAINT);\n',
        '''    /* A retained move skips its owner and repairs only background.
     * Other composition cancels before pixels change. A partially pasted
     * destination expands damage so fallback repairs its whole window. */
    if ((drag_mode & CACHED_MOVE) == 0 || skip_handle != cache_owner) {
        if (cache_phase == UDEKS_CACHE_PASTING) {
            struct udeks_window *cached = window_by_handle(cache_owner);
            if (cached != 0) damage_add(cached);
        }
        cache_invalidate();
    }
    udeks_vic_pointer_busy_begin(UDEKS_VIC_BUSY_REPAINT);
''')
    source = replace(source, '    drag_mode = mode;\n',
        '''    drag_mode = mode;
    if (mode == DRAG_MOVE && cache_phase == UDEKS_CACHE_READY && cache_owner == handle)
        drag_mode |= CACHED_MOVE;
    else cache_invalidate();
''')
    source = replace(source, 'static unsigned char top_window(void)\n{',
        '''static void cache_paint_image(unsigned char handle)
{
    /* READY describes retained pixels, not a finished screen repair. Mark
     * frontend composition busy before erasing; banked flow stays READY. */
    cache_phase |= 0x80u;
    drag_mode |= CACHED_MOVE;
    compose_damage(handle);
    drag_mode = 0;
    if (cache_request(handle, UDEKS_CACHE_COMMAND_PASTE) != UDEKS_CACHE_OK)
        compose_damage(UDEKS_WINDOW_NONE);
}

static unsigned char top_window(void)
{''')
    source = replace(source, '''    dragging_handle = UDEKS_WINDOW_NONE;
    drag_mode = 0;
    compose_damage(UDEKS_WINDOW_NONE);
    udeks_pointer_resynchronize();''',
        '''    dragging_handle = UDEKS_WINDOW_NONE;
    if ((drag_mode & CACHED_MOVE) != 0) {
        cache_paint_image(handle);
    } else {
        drag_mode = 0;
        compose_damage(UDEKS_WINDOW_NONE);
    }
    udeks_pointer_resynchronize();''')
    source = replace(source, 'void udeks_window_manager_reset(void)\n{\n    unsigned char index;\n',
        'void udeks_window_manager_reset(void)\n{\n    unsigned char index;\n\n    cache_invalidate();\n')
    source = replace(source, '''    if (dragging_handle != UDEKS_WINDOW_NONE) {
        return UDEKS_WINDOW_OK;
    }
    damage_set(window);
    compose_damage(UDEKS_WINDOW_NONE);
    return UDEKS_WINDOW_OK;''',
        '''    if (dragging_handle != UDEKS_WINDOW_NONE ||
        cache_phase == UDEKS_CACHE_CAPTURING || cache_phase == UDEKS_CACHE_PASTING) {
        return UDEKS_WINDOW_OK;
    }
    damage_set(window);
    if (cache_phase == UDEKS_CACHE_READY && handle != cache_owner) {
        /* Updating a lower window does not change the top cached image.
         * Recompose its background and restore pixels, not app vertices. */
        damage_add(window_by_handle(cache_owner));
        cache_paint_image(cache_owner);
    } else compose_damage(UDEKS_WINDOW_NONE);
    return UDEKS_WINDOW_OK;''')
    source = replace(source, '''    pointer_x = udeks_pointer_x() - POINTER_X_BIAS;''',
        '''    if (cache_accept_state < 0x80u) cache_accept_poll();
    if (dragging_handle == UDEKS_WINDOW_NONE &&
        (cache_phase == UDEKS_CACHE_CAPTURING || cache_phase == UDEKS_CACHE_PASTING)) {
        unsigned char phase = cache_phase;
        unsigned char budget = 4;
        do {
            /* Each STEP releases its MMU/runtime/IRQ lease before the next.
             * Commit dirty pages once per bounded batch, not once per row. */
            if (cache_step() != UDEKS_CACHE_OK) {
                window = window_by_handle(cache_owner);
                if (window != 0) {
                    damage_set(window);
                    compose_damage(UDEKS_WINDOW_NONE);
                }
                break;
            }
        } while (--budget != 0 && cache_phase == phase);
        if (phase == UDEKS_CACHE_PASTING) udeks_vic_bitmap_commit();
    }
    /* Finish a paste before processing a new click. Pointer motion and
     * console/task polling remain active; a release is not swallowed. */
    if (cache_phase == UDEKS_CACHE_PASTING) return UDEKS_WINDOW_OK;
    pointer_x = udeks_pointer_x() - POINTER_X_BIAS;''')
    return source


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for name, text in (('baseline', BASE.read_text()), ('registers', registered(BASE.read_text())),
                       ('candidate', candidate(BASE.read_text()))):
        source = WORK / (name+'.c'); source.write_text(text)
        subprocess.run(['cl65','-t','none','--cpu','6502','--standard','c99','-Oirs',
            '-I',str(ROOT / 'include'),'-c','-o',str(source.with_suffix('.o')),str(source)],check=True)
        sizes[name] = object_sizes(source.with_suffix('.o'))
    net = sizes['candidate']['CODE']-sizes['baseline']['CODE']
    report = {'qualification':'private C sizing only; no integrated link or GUI cache',
        'sizes':sizes, 'registers_saved':sizes['baseline']['CODE']-sizes['registers']['CODE'],
        'net_manager_bytes':net, 'remaining_after_manager':131-net-6,
        'command_wrapper_bytes':6}
    (WORK / 'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build',))
    parser.parse_args(); build()

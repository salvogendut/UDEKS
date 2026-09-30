# SPDX-License-Identifier: GPL-3.0-or-later
"""Four real window descriptors, not a claim of four runnable disk apps."""
import ast
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def drawing_stubs():
    tree = ast.parse((ROOT / 'tests/test_window_manager_budget.py').read_text())
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == 'test_real_c_manager_matches_baseline_geometry_state_and_all_drawing_calls')
    return next(ast.literal_eval(n.value) for n in method.body if isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'harness').split('int main(void)')[0]


class FourWindowsTests(unittest.TestCase):
    def test_four_owners_focus_click_drag_close_capacity_and_reuse(self):
        extra = r'''
#include <assert.h>
#include <limits.h>
#include <string.h>
static unsigned paints[5], closes[5];
static void owned_paint(unsigned char h) {
    unsigned owner = udeks_window_owner(h);
    assert(owner >= 1 && owner <= 4); ++paints[owner];
}
static void close1(unsigned char h) {(void)h; ++closes[1];}
static void close2(unsigned char h) {(void)h; ++closes[2];}
static void close3(unsigned char h) {(void)h; ++closes[3];}
static void close4(unsigned char h) {(void)h; ++closes[4];}
static udeks_window_close_fn closers[4] = {close1, close2, close3, close4};
static void pointer(unsigned x, unsigned y, unsigned down) {
    px=x+12; py=y+40; buttons=down; udeks_window_manager_poll();
}
static void ranks(void) {
    unsigned seen=0, count=0;
    for (unsigned i=0;i<4;++i) if (windows[i].active) {
        assert(windows[i].z>=1 && windows[i].z<=active_count);
        assert(!(seen & (1u<<windows[i].z)));
        seen |= 1u<<windows[i].z; ++count;
    }
    assert(count==active_count);
}
int main(void) {
    unsigned char handles[4];
    udeks_window_manager_start();
    for (unsigned i=0;i<4;++i) {
        /* Overlapping windows with an exposed client strip per owner. */
        handles[i]=udeks_window_create(i+1,1,2|4|16,i*64,20,96,80,
                                      0,owned_paint,closers[i]);
        assert(handles[i] && udeks_window_owner(handles[i])==i+1);
    }
    assert(active_count==4); ranks();
    unsigned char saved[sizeof windows]; memcpy(saved,windows,sizeof windows);
    unsigned char status[32]; memcpy(status,test_status,sizeof status);
    assert(!udeks_window_create(5,1,6,0,0,96,80,0,owned_paint,close1));
    assert(!memcmp(saved,windows,sizeof windows));
    assert(!memcmp(status,test_status,sizeof status));
    /* Far/wrapping coordinates must reject even with a free descriptor. */
    udeks_window_destroy(handles[3]);
    assert(closes[4]==1 && !udeks_window_owner(handles[3]));
    memcpy(saved,windows,sizeof windows);
    assert(!udeks_window_create(4,1,6,UINT_MAX-31u,0,64,64,0,owned_paint,close4));
    assert(!udeks_window_create(4,1,6,0,0,UINT_MAX,64,0,owned_paint,close4));
    assert(!memcmp(saved,windows,sizeof windows));
    handles[3]=udeks_window_create(4,1,2|4|16,192,20,96,80,0,owned_paint,close4);
    assert(handles[3] && !udeks_window_take_click(handles[3]));
    for (unsigned remaining=4;remaining;--remaining) {
        unsigned i=remaining-1;
        pointer(i*64+8,44,0); pointer(i*64+8,44,1);
        assert(focused_handle==handles[i]); ranks();
        for (unsigned other=0;other<4;++other)
            if (other!=i) assert(!udeks_window_take_click(handles[other]));
        const struct udeks_window_click *click=udeks_window_take_click(handles[i]);
        assert(click && click->x==8 && click->y==24);
        pointer(i*64+8,44,0);
    }
    for (unsigned i=0;i<4;++i) {
        pointer(i*64+8,25,0); pointer(i*64+8,25,1);
        assert(dragging_handle==handles[i]);
        pointer(i*64+8,31,1); pointer(i*64+8,31,0);
        assert(!dragging_handle && windows[handles[i]-1].y==26); ranks();
    }
    for (unsigned i=0;i<4;++i) {
        assert(paints[i+1]);
        assert(!udeks_window_destroy(handles[i]));
        assert(!udeks_window_owner(handles[i]));
        assert(closes[i+1]==(i==3 ? 2 : 1)); ranks();
    }
    assert(!active_count && !focused_handle);
    assert(!udeks_window_owner(0) && !udeks_window_owner(255));
    return 0;
}
'''
        cache_stub = r'''
volatile unsigned char cache_accept_state, cache_owner, cache_phase;
struct udeks_cache_geometry manager_test_geometry;
unsigned char manager_test_owner,manager_test_eligible,manager_test_row_offset;
unsigned char manager_partial_first,manager_partial_end;
unsigned int manager_partial_width;
unsigned char cache_accept_poll(void) {return 1;}
unsigned char cache_command(unsigned char op) {
    (void)op; cache_owner=cache_phase=0; return 0;
}
unsigned char cache_step(void) {return 1;}
'''
        with tempfile.TemporaryDirectory() as directory:
            for filename in ('window_manager.c', 'window_manager_cached.c'):
                with self.subTest(manager=filename):
                    manager = (ROOT / 'src/services/window' / filename).read_text().replace(
                        '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))',
                        'test_status[offset]')
                    source = Path(directory) / filename
                    binary = source.with_suffix('')
                    source.write_text(drawing_stubs().replace('SOURCE', manager) +
                                      (cache_stub if 'cached' in filename else '') + extra)
                    subprocess.run(['cc', '-std=c99', '-D__fastcall__=',
                                    '-DUDEKS_CACHE_MANAGER_HOST_TEST', '-Wno-unknown-pragmas',
                                    '-I', str(ROOT/'include'), str(source), '-o', str(binary)], check=True)
                    subprocess.run([str(binary)], stdout=subprocess.DEVNULL, check=True)

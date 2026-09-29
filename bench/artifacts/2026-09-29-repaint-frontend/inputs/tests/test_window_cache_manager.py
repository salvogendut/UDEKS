# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_cache_manager import BASE, registered, candidate


def compile_run(work, name, text, extra=()):
    source = work / (name+'.c'); source.write_text(text)
    run = subprocess.run(['cc','-std=c99','-D__fastcall__=','-Wno-unknown-pragmas',
        '-I',str(ROOT / 'include'), str(source), *map(str,extra), '-o',str(work / name)],
        capture_output=True,text=True)
    if run.returncode: raise AssertionError(run.stderr)
    return subprocess.check_output([str(work / name)],stderr=subprocess.STDOUT)


class WindowCacheManagerTests(unittest.TestCase):
    def test_register_variant_preserves_complete_drawing_and_state_trace(self):
        tree = ast.parse((ROOT / 'tests/test_window_manager_budget.py').read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and
            n.name=='test_real_c_manager_matches_baseline_geometry_state_and_all_drawing_calls')
        harness = next(ast.literal_eval(n.value) for n in method.body if isinstance(n,ast.Assign)
                       and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='harness')
        with tempfile.TemporaryDirectory() as name:
            work=Path(name); traces=[]
            for label, source in (('baseline',BASE.read_text()),('registers',registered(BASE.read_text()))):
                source=source.replace('(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))',
                                      'test_status[offset]')
                traces.append(compile_run(work,label,harness.replace('SOURCE',source)))
            self.assertEqual(*traces)

    def test_bounded_capture_move_repeated_paste_and_invalidation_fallback(self):
        harness=r'''
#include <assert.h>
#include <string.h>
static unsigned char test_status[32];
SOURCE
volatile unsigned char cache_accept_state=0x80,cache_owner,cache_phase;
struct udeks_cache_geometry manager_test_geometry;
unsigned char manager_test_owner,manager_test_eligible;
static struct udeks_cache_lease lease;
static unsigned captures,pastes,rows,paints;
static unsigned px=164,py=134,buttons;
unsigned char cache_accept_poll(void) {return 0;}
unsigned char cache_command(unsigned char op) {
 unsigned char result=0;
 switch(op) {
 case 0:udeks_cache_init(&lease,2224);break;
 case 1:udeks_cache_invalidate(&lease,0);break;
 case 2:result=udeks_cache_capture_begin(&lease,manager_test_owner,1,&manager_test_geometry,manager_test_eligible);
   if(!result)++captures;break;
 case 3:result=udeks_cache_paste_begin(&lease,manager_test_owner,1,&manager_test_geometry);
   if(!result)++pastes;break;
 default:assert(0);
 }
 if(!result){cache_owner=lease.owner;cache_phase=lease.phase;}return result;
}
unsigned char cache_step(void) {
 struct udeks_cache_row row;
 unsigned char result=udeks_cache_prepare_row(&lease,lease.owner,1,&row);
 if(!result) {++rows;result=udeks_cache_commit_row(&lease,lease.owner,1,lease.row);}
 if(!result)cache_phase=lease.phase;return result;
}
void udeks_vic_bitmap_set_clip(int x,int y,int w,int h){(void)x;(void)y;(void)w;(void)h;}
void udeks_vic_bitmap_reset_clip(void){}
void udeks_vic_bitmap_commit(void){}
void udeks_vic_bitmap_fill(int x,int y,int w,int h,unsigned char c){(void)x;(void)y;(void)w;(void)h;(void)c;}
void udeks_vic_bitmap_pixel(int x,int y,unsigned char c){(void)x;(void)y;(void)c;}
void udeks_vic_bitmap_line(int x,int y,int xx,int yy,unsigned char c){(void)x;(void)y;(void)xx;(void)yy;(void)c;}
void udeks_vic_bitmap_rectangle(int x,int y,int w,int h,unsigned char c){(void)x;(void)y;(void)w;(void)h;(void)c;}
void udeks_vic_pointer_busy_begin(unsigned char r){(void)r;}
void udeks_vic_pointer_busy_end(unsigned char r){(void)r;}
void udeks_vic_bitmap_outline_toggle(unsigned x,unsigned char y,unsigned w,unsigned char h){(void)x;(void)y;(void)w;(void)h;}
void udeks_vic_bitmap_outline_move(unsigned x,unsigned char y,unsigned xx,unsigned char yy,unsigned w,unsigned char h)
{(void)x;(void)y;(void)xx;(void)yy;(void)w;(void)h;}
unsigned char udeks_vic_graphics_is_active(void){return 1;}
unsigned int udeks_pointer_x(void){return px;}
unsigned char udeks_pointer_y(void){return py;}
unsigned char udeks_pointer_buttons(void){return buttons;}
void udeks_pointer_resynchronize(void){}
static void paint(unsigned char h){(void)h;++paints;}
static void drive(void) {
 unsigned remaining=104-lease.row;
 for(unsigned i=0;i<remaining;i+=4){unsigned before=rows;udeks_window_manager_poll();
   assert(rows==before+(remaining-i<4?remaining-i:4));}
 assert(cache_phase==2);
}
int main(void) {
 udeks_cache_init(&lease,2224);udeks_window_manager_start();
 unsigned h=udeks_window_create(2,1,15,144,88,168,104,0,paint,0);
 assert(h==1 && captures==0);
 assert(udeks_window_image_complete(h)==0 && captures==1 && cache_phase==1);
 assert(udeks_window_begin_paint(h)==1); /* Source frozen across polls. */
 drive();assert(rows==104);
 for(unsigned move=0;move<2;++move) {
   unsigned before=paints;
   begin_drag(h,windows[0].x+8,windows[0].y+5,DRAG_MOVE);
   assert(drag_mode==0x81 && cache_phase==2);
   drag_x=move?7:60;drag_y=move?7:40;finish_drag();
   assert(pastes==move+1 && cache_phase==3 && paints==before);
   assert(udeks_window_begin_paint(h)==1); /* Destination frozen. */
   drive();assert(rows==104*(move+2));
 }
 /* A resize invalidates and falls back to normal paint. */
 begin_drag(h,20,20,DRAG_RESIZE);assert(cache_phase==0);
 drag_width=200;finish_drag();assert(cache_phase==0 && paints>0);
 assert(udeks_window_image_complete(h)==0 && cache_phase==0); /* oversized */
 windows[0].width=168;udeks_window_image_complete(h);assert(cache_phase==1);
 begin_drag(h,20,20,DRAG_MOVE);assert(cache_phase==0 && drag_mode==1);finish_drag();
 /* Content and handle reuse cancel ownership, including a partial paste. */
 udeks_window_image_complete(h);drive();
 begin_drag(h,20,20,DRAG_MOVE);finish_drag();cache_step();assert(cache_phase==3);
 udeks_window_repaint(h);assert(cache_phase==3); /* Destination frozen: deferred repaint. */
 drive();udeks_window_repaint(h);assert(cache_phase==0);
 udeks_window_image_complete(h);drive();
 begin_drag(h,20,20,DRAG_MOVE);
 udeks_window_create(1,1,15,0,0,64,64,0,paint,0);assert(cache_phase==0);
 finish_drag();assert(cache_phase==0); /* Creation during drag cannot retain stale image. */
 udeks_window_destroy(h);assert(cache_owner==0);
 udeks_window_manager_reset();assert(cache_phase==0);
}
'''
        source=candidate(BASE.read_text()).replace(
            '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))','test_status[offset]')
        with tempfile.TemporaryDirectory() as name:
            work=Path(name)
            compile_run(work,'candidate','#define UDEKS_CACHE_MANAGER_HOST_TEST\n'+harness.replace('SOURCE',source),
                        (ROOT / 'src/services/window/move_cache_state.c',))

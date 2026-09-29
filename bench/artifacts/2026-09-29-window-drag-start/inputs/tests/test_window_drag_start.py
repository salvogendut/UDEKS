# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from window_drag_start import candidate
from window_cache_partial_manager import candidate as parent
from window_cache_manager import BASE,replace
from test_window_cache_manager import compile_run
from test_window_cache_partial_manager import transport


class DragStartTests(unittest.TestCase):
    def test_deferred_client_calls_and_complete_canvas_after_release(self):
        harness=transport((ROOT/'bench/window-cache-manager/occlusion-host.inc').read_text())
        extra=r'''
 /* Drag the clock over a completed lower wave. Only the button path changes:
  * no application callbacks, blank old rectangle, outline while held. */
 for(unsigned mode=1;mode<=2;++mode){
   udeks_window_manager_reset();memset(screen,0,sizeof(screen));content=1;
   unsigned wave=udeks_window_create(2,1,15,144,88,168,104,0,paint,0);
   unsigned clock=udeks_window_create(1,1,15,124,61,72,77,0,paint,0);
   unsigned wc=calls[wave],cc=calls[clock];
   begin_drag(clock,132,66,mode);
   if(DEFERRED){
     assert(calls[wave]==wc && calls[clock]==cc);
     for(unsigned y=61;y<138;++y)for(unsigned x=124;x<196;++x)assert(screen[y][x]==0);
   }
   if(mode==1){drag_x=150;drag_y=76;}else{drag_width=96;drag_height=88;}
   finish_drag();assert(calls[wave]==wc+(DEFERRED?1:2) && calls[clock]==cc+1);dump();
 }
 /* Closing during an outline repairs the exposed lower window as usual. */
 udeks_window_manager_reset();memset(screen,0,sizeof(screen));
 unsigned wave=udeks_window_create(2,1,15,144,88,168,104,0,paint,0);
 unsigned clock=udeks_window_create(1,1,15,124,61,72,77,0,paint,0);
 begin_drag(clock,132,66,1);udeks_window_destroy(clock);assert(!dragging_handle);dump();
 /* Erasing a retained wave's display must not invalidate its saved image. */
 udeks_window_manager_reset();memset(screen,0,sizeof(screen));
 wave=udeks_window_create(2,1,15,144,88,168,104,0,paint,0);
 udeks_window_image_complete(wave);drive();unsigned wc=calls[wave];
 begin_drag(wave,152,93,1);assert(cache_phase==2);
 drag_x=20;drag_y=30;finish_drag();drive();assert(calls[wave]==wc);dump();
'''
        harness=replace(harness,' return 0;\n}',extra+' return 0;\n}')
        with tempfile.TemporaryDirectory() as directory:
            outputs=[]
            for label,transform in (('reference',parent),('deferred',candidate)):
                source=transform(BASE.read_text()).replace(
                    '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))','test_status[offset]')
                prefix='#define UDEKS_CACHE_MANAGER_HOST_TEST\n#define OPTIMIZED 1\n'
                prefix+=f'#define DEFERRED {int(label=="deferred")}\n'
                outputs.append(compile_run(Path(directory),label,prefix+harness.replace('SOURCE',source),
                    (ROOT/'src/services/window/move_cache_state.c',)))
            self.assertEqual(*outputs)

    def test_erase_only_uses_existing_compositor_without_new_state(self):
        source=candidate(BASE.read_text())
        begin=source[source.index('static void begin_drag('):source.index('static void move_drag(')]
        self.assertIn('compose_damage(255u);',begin)
        self.assertNotIn('compose_damage(handle);',begin)
        self.assertIn('skip_handle != 255u && rank <= active_count',source)
        self.assertIn('unsigned char budget = 4;',source)
        self.assertEqual(source.count('#pragma bss-name'),BASE.read_text().count('#pragma bss-name'))

if __name__=='__main__':unittest.main()

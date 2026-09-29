# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import unittest
import sys
import tempfile
from unittest.mock import patch
import test_repaint_chrome_rows as row_tests
import test_repaint_raster as raster_tests
from test_window_cache_manager import compile_run
from test_window_cache_partial_manager import transport

ROOT = Path(__file__).resolve().parents[1]
READ_TEXT = Path.read_text
sys.path.insert(0,str(ROOT / 'tools'))
import window_repaint_raster as budget


def compact_fragment(path, *args, **kwargs):
    if path == ROOT / 'bench/window-repaint-lane/chrome.inc':
        return READ_TEXT(ROOT / 'bench/window-repaint-raster/chrome.inc', *args, **kwargs)
    if path == ROOT / 'bench/window-repaint-lane/raster.inc':
        fragment = READ_TEXT(ROOT / 'bench/window-repaint-raster/raster.inc', *args, **kwargs)
        dispatch = READ_TEXT(ROOT / 'bench/window-repaint-bank/dispatch.c').replace('#include "packet.h"','')
        return fragment + '\n#define REPAINT_HOST\n#include "' + str(ROOT / 'bench/window-repaint-raster/receipt.c') + '"\n' + dispatch + '''
struct repaint_packet repaint_packet;
unsigned char private_repaint_policy_call(void) { repaint_dispatch(); return packet.result; }
'''
    return READ_TEXT(path, *args, **kwargs)


class CompactRasterTests(unittest.TestCase):
    def test_independent_native_oracle_matches_original_full_window_not_new_rows(self):
        source=READ_TEXT(budget.SOURCE).replace(
            '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))','test_status[offset]')
        harness=transport(READ_TEXT(ROOT / 'bench/window-cache-manager/occlusion-host.inc')).split('int main(void){',1)[0]
        cases=','.join('{'+','.join(map(str,c))+'}' for c in budget.CASES)
        harness+='''
int main(void) {
 static const unsigned cases[8][5]={'''+cases+'''};
 static unsigned char title[96],image[8000]; memset(title,'M',sizeof(title));
 for(unsigned c=0;c<8;++c){
  struct udeks_window w={0}; w.x=cases[c][0];w.y=cases[c][1];w.width=cases[c][2];w.height=cases[c][3];w.flags=cases[c][4];
  w.title=c==0?0:(c==5?title:(const unsigned char *)"aZ ? Xclock");
  memset(screen,0,sizeof(screen));udeks_vic_bitmap_reset_clip();
  udeks_vic_bitmap_fill(w.x,w.y,w.width,w.height,7);draw_chrome(&w);
  for(unsigned y=w.y+14;y<w.y+w.height-3;++y)
   for(unsigned x=w.x+3;x<w.x+w.width-3;++x)
    udeks_vic_bitmap_pixel(x,y,(x*3+y*5)%7<3?0:7);
  memset(image,0,sizeof(image));
  for(unsigned y=0;y<200;++y)for(unsigned x=0;x<320;++x)
   if(screen[y][x])image[(y&248)*40+(x&~7)+(y&7)]|=128>>(x&7);
  fwrite(image,1,8000,stdout);
 }
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as name:
            out=compile_run(Path(name),'oracle','#define UDEKS_CACHE_MANAGER_HOST_TEST\n'+
                harness.replace('SOURCE',source),(ROOT / 'src/services/window/move_cache_state.c',))
        self.assertEqual(out,b''.join(budget.reference(i) for i in range(8)))
    def test_compact_chrome_against_original_full_canvas_and_all_clips(self):
        with patch.object(Path, 'read_text', compact_fragment):
            row_tests.RepaintChromeRowsTests().test_one_row_chrome_matches_original_glyphs_borders_buttons_and_all_clips()

    def test_compact_backend_preserves_bounds_stale_rejection_and_complete_pixels(self):
        with patch.object(Path, 'read_text', compact_fragment):
            raster_tests.RepaintRasterTests().test_real_row_backend_bounds_clips_commit_pages_stale_work_and_delegated_clients()

# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import tempfile
import unittest

from test_window_cache_manager import compile_run
from test_window_cache_partial_manager import transport

ROOT = Path(__file__).resolve().parents[1]


class RepaintChromeRowsTests(unittest.TestCase):
    def test_one_row_chrome_matches_original_glyphs_borders_buttons_and_all_clips(self):
        source = (ROOT / 'src/services/window/window_manager_cached.c').read_text().replace(
            '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))', 'test_status[offset]')
        harness = transport((ROOT / 'bench/window-cache-manager/occlusion-host.inc').read_text())
        harness = harness.split('int main(void){', 1)[0]
        harness = harness.replace('static unsigned fills,commits,calls[5],paste_requests;',
            'static unsigned fills,commits,calls[5],paste_requests,pixel_calls;\nstatic int tracked_row=-1;')
        harness = harness.replace(' ++fills;\n',
            ' ++fills;\n if(tracked_row>=0){assert(y==tracked_row && h==1 && w<=320);}\n')
        harness = harness.replace(' if(x>=0 && x<320',
            ' if(tracked_row>=0){assert(y==tracked_row);++pixel_calls;}\n if(x>=0 && x<320')
        # Fill's mock raster uses pixel calls itself, unlike the real span
        # primitive. Count direct decoration pixels independently of spans.
        harness = harness.replace(' for(int yy=y;yy<y+h;++yy)for(int xx=x;xx<x+w;++xx)udeks_vic_bitmap_pixel(xx,yy,c);',
            ' unsigned count=pixel_calls;\n for(int yy=y;yy<y+h;++yy)for(int xx=x;xx<x+w;++xx)udeks_vic_bitmap_pixel(xx,yy,c);\n pixel_calls=count;')
        harness += (ROOT / 'bench/window-repaint-lane/chrome.inc').read_text()
        harness += r'''
int main(void) {
 static unsigned char expected[200][320],title[96];
 static const unsigned char *titles[]={0,(const unsigned char *)"aZ ? Xclock",title};
 static const unsigned widths[]={16,17,48,64,168,320};
 static const unsigned heights[]={18,48,104,200};
 memset(title,'M',sizeof(title)); /* Width bounds an unterminated long title. */
 for(unsigned wi=0;wi<6;++wi)for(unsigned hi=0;hi<4;++hi)
 for(unsigned edge=0;edge<2;++edge)for(unsigned flags=0;flags<16;++flags)
 for(unsigned ti=0;ti<3;++ti)for(unsigned clip=0;clip<4;++clip) {
  struct udeks_window w={0};w.x=edge?320-widths[wi]:0;w.y=edge?200-heights[hi]:0;
  w.width=widths[wi];w.height=heights[hi];w.flags=flags;w.title=titles[ti];
  memset(screen,0x01,sizeof(screen));
  switch(clip) {
   case 0:udeks_vic_bitmap_reset_clip();break;
   case 1:udeks_vic_bitmap_set_clip(w.x+4,w.y+3,w.width-8,12);break;
   case 2:udeks_vic_bitmap_set_clip(w.x+w.width-3,w.y+1,2,w.height-2);break;
   case 3:udeks_vic_bitmap_set_clip(w.x,w.y+w.height-4,w.width,3);break;
  }
  udeks_vic_bitmap_fill(w.x,w.y,w.width,w.height,7);draw_chrome(&w);
  memcpy(expected,screen,sizeof(screen));memset(screen,0x01,sizeof(screen));
  for(unsigned row=0;row<w.height;++row) {
   fills=pixel_calls=0;tracked_row=w.y+row;draw_chrome_row(&w,row);tracked_row=-1;
   assert(fills<=3 && pixel_calls<=250);
  }
  assert(memcmp(expected,screen,sizeof(screen))==0);
 }
 puts("row chrome pixels/bounds OK");return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            output = compile_run(Path(directory), 'chrome', '#define UDEKS_CACHE_MANAGER_HOST_TEST\n' +
                harness.replace('SOURCE', source), (ROOT / 'src/services/window/move_cache_state.c',))
        self.assertEqual(output, b'row chrome pixels/bounds OK\n')


if __name__ == '__main__':
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import tempfile
import unittest

from test_window_cache_manager import compile_run
from test_window_cache_partial_manager import transport

ROOT = Path(__file__).resolve().parents[1]


class RepaintRasterTests(unittest.TestCase):
    def test_real_row_backend_bounds_clips_commit_pages_stale_work_and_delegated_clients(self):
        source = (ROOT / 'src/services/window/window_manager_cached.c').read_text().replace(
            '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))', 'test_status[offset]')
        harness = transport((ROOT / 'bench/window-cache-manager/occlusion-host.inc').read_text()).split('int main(void){', 1)[0]
        harness = harness.replace(' if(x>=0 && x<320 && y>=0 && y<200 && x>=cx0 && x<cx1 && y>=cy0 && y<cy1)screen[y][x]=(c==0);',
            ''' if(x>=0 && x<320 && y>=0 && y<200 && x>=cx0 && x<cx1 && y>=cy0 && y<cy1) {
 screen[y][x]=(c==0);repaint_dirty[(((y&248)*40)+(x&~7)+(y&7))>>8]=1;
 }''')
        harness = '''static unsigned char repaint_dirty[32];
#define REPAINT_DIRTY_MAP repaint_dirty
''' + harness
        harness += (ROOT / 'bench/window-repaint-lane/chrome.inc').read_text()
        harness += (ROOT / 'bench/window-repaint-lane/raster.inc').read_text()
        harness += r'''
static unsigned char display[200][320],expected[200][320],shadow_before[200][320],display_before[200][320];
static unsigned page_calls,page_seen[32];
static unsigned char dirty_before[32];
void udeks_vic_bitmap_commit_page(unsigned char page) {
 assert(page<32);++page_calls;++page_seen[page];
 for(unsigned off=page*256;off<(page+1)*256 && off<8000;++off) {
  unsigned y=(off/320)*8+off%8,x=((off%320)/8)*8;
  memcpy(&display[y][x],&screen[y][x],8);
 }
}
static void client_row(unsigned y,struct udeks_repaint_rect clip) {
 for(unsigned x=clip.left;x<clip.right;++x)
  udeks_vic_bitmap_pixel(x,y,(x*3+y*5)%7<3?0:7);
}
static void unchanged(unsigned fills_before,unsigned pages_before,struct udeks_repaint_lane old) {
 assert(fills==fills_before && page_calls==pages_before);
 assert(memcmp(&old,&udeks_repaint_lane,sizeof(old))==0);
 assert(memcmp(dirty_before,repaint_dirty,sizeof(repaint_dirty))==0);
 assert(cx0==111 && cy0==77 && cx1==113 && cy1==80);
}
int main(void) {
 struct udeks_repaint_window view={{10,110,10,110},1,1,1};
 struct udeks_repaint_rect full={0,320,0,200};
 struct udeks_repaint_lane_work work;
 struct udeks_window *w=&windows[0];
 w->active=1;w->z=1;w->x=10;w->y=10;w->width=100;w->height=100;
 w->flags=13;w->title=(const unsigned char *)"Xclock";w->paint=paint;
 udeks_vic_bitmap_reset_clip();memset(screen,0,sizeof(screen));
 udeks_vic_bitmap_fill(10,10,100,100,7);draw_chrome(w);
 struct udeks_repaint_rect client={13,107,24,107};
 for(unsigned y=24;y<107;++y)client_row(y,client);
 memcpy(expected,screen,sizeof(screen));
 memset(screen,0,sizeof(screen));memset(repaint_dirty,0,sizeof(repaint_dirty));
 udeks_lane_init();assert(udeks_lane_request(&full)==0);
 unsigned polls=0,clear_steps=0,chrome_steps=0,client_steps=0,commit_steps=0;
 while(1) {
  unsigned result=udeks_lane_peek(&view,1,&work);
  if(result==1)break;
  if(result==5)continue;
  assert(result==0 && ++polls<1000);
  udeks_vic_bitmap_set_clip(111,77,2,3);
  unsigned pages_before=page_calls,fills_before=fills;
  struct udeks_repaint_lane old=udeks_repaint_lane;
  memcpy(dirty_before,repaint_dirty,sizeof(repaint_dirty));
  result=lane_raster_step(&work);
  switch(work.ticket.phase) {
   case 1:assert(result==0 && fills==fills_before+1 && work.clip.bottom-work.clip.top<=4);++clear_steps;break;
   case 3:assert(result==0 && fills-fills_before<=3);++chrome_steps;break;
   case 4:
    assert(result==UDEKS_LANE_BACKEND_REQUIRED);unchanged(fills_before,pages_before,old);
    assert(calls[1]==0); /* The legacy callback was not run/replayed. */
    assert(udeks_lane_validate(&work.ticket)==0);
    udeks_vic_bitmap_set_clip(work.clip.left,work.clip.top,work.clip.right-work.clip.left,work.clip.bottom-work.clip.top);
    unsigned y=work.clip.top+work.ticket.cursor;assert(y<work.clip.bottom);
    client_row(y,work.clip);udeks_vic_bitmap_reset_clip();
    assert(udeks_lane_ack(&work.ticket,y+1<work.clip.bottom)==0);++client_steps;break;
   case 6:assert(result==0 && page_calls-pages_before<=1);++commit_steps;break;
   default:assert(0);
  }
  assert(cx0==0 && cy0==0 && cx1==320 && cy1==200);
  if(work.ticket.phase!=6)assert(page_calls==pages_before);
 }
 assert(clear_steps==50 && chrome_steps==100 && client_steps==83 && commit_steps==32);
 assert(page_calls==32 && calls[1]==0);
 for(unsigned p=0;p<32;++p)assert(page_seen[p]==1 && repaint_dirty[p]==0);
 assert(memcmp(expected,screen,sizeof(screen))==0);
 assert(memcmp(expected,display,sizeof(display))==0);

 /* Withdraw BEFORE changing the table/slot. Stale work must not read the
  * replaced title, touch pixels, clip, dirty map, cache or acknowledge. */
 assert(udeks_lane_request(&full)==0);
 for(unsigned limit=0;;++limit) {
  assert(limit<100 && udeks_lane_peek(&view,1,&work)==0);
  if(work.ticket.phase==3 && work.ticket.cursor==4)break; /* A glyph row would dereference title. */
  assert(lane_raster_step(&work)==0);
 }
 memcpy(shadow_before,screen,sizeof(screen));memcpy(display_before,display,sizeof(display));
 assert(udeks_lane_changed(&full)==0);w->title=(const unsigned char *)1;
 udeks_vic_bitmap_set_clip(111,77,2,3);
 unsigned pages_before=page_calls,fills_before=fills;
 struct udeks_repaint_lane old=udeks_repaint_lane;
 memcpy(dirty_before,repaint_dirty,sizeof(repaint_dirty));
 assert(lane_raster_step(&work)==UDEKS_REPAINT_STALE);unchanged(fills_before,pages_before,old);
 assert(memcmp(shadow_before,screen,sizeof(screen))==0);
 assert(memcmp(display_before,display,sizeof(display))==0);
 w->title=(const unsigned char *)"Xclock";

 /* Retained RESTORE is delegated too: only the real lease provider can
  * verify/advance it. No image pointer/cache transport is stored or invoked. */
 udeks_lane_init();udeks_repaint_lane.current=view.bounds;
 udeks_repaint_lane.state=5;udeks_repaint_lane.selector=9;
 work.ticket.epoch=1;work.ticket.cursor=0;work.ticket.phase=5;work.ticket.selector=9;work.clip=view.bounds;
 old=udeks_repaint_lane;
 assert(lane_raster_step(&work)==UDEKS_LANE_BACKEND_REQUIRED);unchanged(fills_before,pages_before,old);
 /* A forged out-of-bounds page with an otherwise live private receipt fails
  * before any shared-state mutation. A clean page commits no bytes. */
 udeks_repaint_lane.state=6;udeks_repaint_lane.cursor=32;
 work.ticket.phase=6;work.ticket.cursor=32;old=udeks_repaint_lane;
 assert(lane_raster_step(&work)==UDEKS_REPAINT_INVALID);unchanged(fills_before,pages_before,old);
 udeks_repaint_lane.cursor=0;work.ticket.cursor=0;
 repaint_dirty[0]=0; /* Explicit clean-page fixture after the new partial repair. */
 assert(lane_raster_step(&work)==0 && page_calls==pages_before);
 assert(cx0==0 && cy0==0 && cx1==320 && cy1==200);
 puts("bounded raster/clip/page/cancellation/delegation OK");return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            output = compile_run(Path(directory), 'raster', '#define UDEKS_CACHE_MANAGER_HOST_TEST\n' +
                harness.replace('SOURCE', source), (ROOT / 'src/services/window/move_cache_state.c',
                    ROOT / 'src/services/window/repaint_lane.c'))
        self.assertEqual(output, b'bounded raster/clip/page/cancellation/delegation OK\n')


if __name__ == '__main__':
    unittest.main()

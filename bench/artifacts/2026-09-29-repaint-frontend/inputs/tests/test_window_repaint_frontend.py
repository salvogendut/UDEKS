# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import tempfile
import unittest

from test_window_cache_manager import compile_run
from test_window_cache_partial_manager import transport

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from window_repaint_compact import candidate


def harness():
    source = candidate((ROOT / 'src/services/window/window_manager_cached.c').read_text()).replace(
        '(*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))', 'test_status[offset]')
    code = transport((ROOT / 'bench/window-cache-manager/occlusion-host.inc').read_text()).split('int main(void){', 1)[0]
    code = code.replace('w->owner==1?content:0', 'content')
    code = code.replace('unsigned char udeks_vic_graphics_is_active(void){return 1;}',
        'static unsigned char graphics_active=1;\nunsigned char udeks_vic_graphics_is_active(void){return graphics_active;}')
    code = code.replace('screen[y][x]=(c==0);',
        '{screen[y][x]=(c==0);repaint_dirty[(((y&248)*40)+(x&~7)+(y&7))>>8]=1;}')
    code = '#define UDEKS_CACHE_MANAGER_HOST_TEST\nstatic unsigned char repaint_dirty[32];\n#define REPAINT_DIRTY_MAP repaint_dirty\n' + code.replace('SOURCE', source)
    code += (ROOT / 'bench/window-repaint-raster/chrome.inc').read_text()
    code += (ROOT / 'bench/window-repaint-raster/raster.inc').read_text()
    code += '\n#define REPAINT_HOST\n#include "' + str(ROOT / 'bench/window-repaint-raster/receipt.c') + '"\n'
    code += (ROOT / 'bench/window-repaint-bank/dispatch.c').read_text().replace('#include "packet.h"', '')
    code += '''
struct repaint_packet repaint_packet;
static unsigned policy_calls, page_calls;
static unsigned char display[200][320], expected[200][320];
unsigned char private_repaint_policy_call(void) { ++policy_calls; repaint_dispatch(); return packet.result; }
void udeks_vic_bitmap_commit_page(unsigned char p) {
 assert(p<32);++page_calls;
 for(unsigned off=p*256;off<(p+1)*256 && off<8000;++off){
  unsigned y=(off/320)*8+off%8,x=((off%320)/8)*8;
  memcpy(&display[y][x],&screen[y][x],8);
 }
}
'''
    code += (ROOT / 'bench/window-repaint-frontend/frontend.inc').read_text().replace('#include "../window-repaint-bank/packet.h"', '')
    code += '''
static void scene(void) {
 memset(windows,0,sizeof(windows));active_count=2;
 windows[1].z=2;windows[1].flags=31;windows[1].x=256;windows[1].y=96;
 windows[1].width=64;windows[1].height=104;windows[1].title=(const unsigned char *)"top";windows[1].paint=paint;
 windows[3].z=1;windows[3].flags=31;windows[3].x=220;windows[3].y=80;
 windows[3].width=100;windows[3].height=100;windows[3].title=(const unsigned char *)"lower";windows[3].paint=paint;
}
static void row_client(const struct udeks_repaint_lane_work *w) {
 unsigned y=w->clip.top+w->ticket.cursor;
 assert(y<w->clip.bottom && repaint_receipt_validate(&w->ticket)==0);
 udeks_vic_bitmap_set_clip(w->clip.left,w->clip.top,w->clip.right-w->clip.left,w->clip.bottom-w->clip.top);
 for(unsigned x=w->clip.left;x<w->clip.right;++x)udeks_vic_bitmap_pixel(x,y,(x*3+y*5)%7<3?0:7);
 udeks_vic_bitmap_reset_clip();assert(repaint_receipt_ack(&w->ticket,y+1<w->clip.bottom)==0);
}
'''
    return code


def run(body):
    with tempfile.TemporaryDirectory() as directory:
        return compile_run(Path(directory), 'frontend', harness() + body,
            (ROOT / 'src/services/window/move_cache_state.c', ROOT / 'src/services/window/repaint_lane.c'))


class RepaintFrontendTests(unittest.TestCase):
    def test_pending_damage_and_sparse_visibility_do_not_revoke_live_work(self):
        self.assertEqual(run(r'''
int main(void){
 struct udeks_repaint_rect full={0,320,0,200},small={0,16,0,18},invalid={319,321,0,18};
 struct udeks_repaint_lane_work work;scene();udeks_vic_bitmap_reset_clip();
 for(unsigned i=0;i<4;++i){
  windows[i].z=i+1;windows[i].flags=31;windows[i].x=0;windows[i].y=0;
  windows[i].width=48;windows[i].height=48;windows[i].title=0;
 }
 windows[1].flags=0; /* live but hidden: must not publish a visible view */
 assert(repaint_frontend_control(0,0,1)==0 && repaint_frontend_control(1,&full,1)==0);
 assert(repaint_frontend_poll(1,&work)==0 && packet.count==3);
 assert(packet.windows[0].handle==1 && packet.windows[1].handle==3 && packet.windows[2].handle==4);
 /* Obtain, don't execute, the current work receipt. Queueing does not fence it. */
 packet.op=REPAINT_PEEK;assert(private_repaint_policy_call()==0);work=packet.work;
 assert(repaint_frontend_control(1,&small,1)==0 && repaint_receipt_validate(&work.ticket)==0);
 struct udeks_repaint_lane saved=udeks_repaint_lane;
 assert(repaint_frontend_control(2,&invalid,1)==2);
 assert(memcmp(&saved,&udeks_repaint_lane,sizeof(saved))==0 && repaint_receipt_validate(&work.ticket)==0);
 assert(repaint_frontend_control(2,&small,1)==0 && repaint_receipt_validate(&work.ticket)==3);
 udeks_repaint_lane.epoch=65535;
 assert(repaint_frontend_control(2,&small,1)==4);
 unsigned before=page_calls;assert(repaint_frontend_poll(1,&work)==4 && page_calls==before);
 puts("pending visibility fences exhaustion OK");return 0;
}
'''), b'pending visibility fences exhaustion OK\n')

    def test_rejected_leases_and_resource_conflicts_do_not_publish_or_draw(self):
        self.assertEqual(run(r'''
int main(void){
 struct udeks_repaint_rect full={0,320,0,200};struct udeks_repaint_lane_work work,before;
 scene();udeks_lane_init();assert(udeks_lane_request(&full)==0);
 memset(&work,0x69,sizeof(work));before=work;
 struct repaint_packet saved; memset(&packet,0x5a,sizeof(packet));saved=packet;
 struct udeks_repaint_lane state=udeks_repaint_lane;
 udeks_vic_bitmap_set_clip(111,77,2,3);
 for(unsigned n=0;n<12;++n){
  unsigned char lease=1;cache_accept_state=0x80;cache_phase=0;dragging_handle=0;graphics_active=1;
  if(n<4)lease=(unsigned char[]){0,2,3,255}[n];
  else if(n==4)cache_accept_state=0;
  else if(n==5)cache_accept_state=255;
  else if(n==6)cache_phase=1;
  else if(n==7)cache_phase=3;
  else if(n==8)graphics_active=0;
  else cache_phase=(unsigned char[]){0x82,4,255}[n-9];
  assert(repaint_frontend_control(REPAINT_CHANGED,&full,lease)==7);
  assert(repaint_frontend_poll(lease,&work)==7);
  assert(memcmp(&saved,&packet,sizeof(packet))==0 && memcmp(&work,&before,sizeof(work))==0);
  assert(memcmp(&state,&udeks_repaint_lane,sizeof(state))==0 && policy_calls==0 && fills==0 && page_calls==0);
  assert(cx0==111 && cy0==77 && cx1==113 && cy1==80);
 }
 cache_accept_state=0x80;cache_phase=0;graphics_active=1;dragging_handle=2;
 assert(repaint_frontend_poll(1,&work)==7 && memcmp(&saved,&packet,sizeof(packet))==0);
 assert(repaint_frontend_control(255,&full,1)==2 && repaint_frontend_control(1,0,1)==2);
 assert(repaint_frontend_poll(1,0)==2 && policy_calls==0);
 puts("resource conflicts atomic OK");return 0;
}
'''), b'resource conflicts atomic OK\n')

    def test_actual_view_packing_order_canvas_and_one_step_poll(self):
        self.assertEqual(run(r'''
int main(void){
 struct udeks_repaint_rect full={0,320,0,200};struct udeks_repaint_lane_work work;
 scene();udeks_vic_bitmap_reset_clip();memset(screen,0,sizeof(screen));
 /* Independent old full-window composition, in rank order. */
 for(unsigned rank=1;rank<=2;++rank)for(unsigned i=0;i<4;++i)if(windows[i].z==rank){
  struct udeks_window *w=&windows[i];udeks_vic_bitmap_fill(w->x,w->y,w->width,w->height,7);draw_chrome(w);
  struct udeks_repaint_lane_work client={0};client.clip.left=w->x+3;client.clip.right=w->x+w->width-3;
  client.clip.top=w->y+14;client.clip.bottom=w->y+w->height-3;
  for(unsigned y=client.clip.top;y<client.clip.bottom;++y)
   for(unsigned x=client.clip.left;x<client.clip.right;++x)udeks_vic_bitmap_pixel(x,y,(x*3+y*5)%7<3?0:7);
 }
 memcpy(expected,screen,sizeof(screen));memset(screen,0,sizeof(screen));
 memset(repaint_dirty,0,sizeof(repaint_dirty));fills=page_calls=0;
 assert(repaint_frontend_control(REPAINT_INIT,0,1)==0);
 assert(repaint_frontend_control(REPAINT_REQUEST,&full,1)==0);
 unsigned clears=0,chrome=0,clients=0,pages=0,polls=0;
 while(1){
  unsigned f=fills,p=page_calls;
  unsigned result=repaint_frontend_poll(1,&work);assert(++polls<1000);
  if(result==1)break;if(result==5)continue;
  assert(packet.count==2 && packet.windows[0].handle==2 && packet.windows[0].rank==2);
  assert(packet.windows[1].handle==4 && packet.windows[1].rank==1);
  assert(packet.windows[0].bounds.right==320 && packet.windows[0].bounds.bottom==200);
  assert(packet.windows[0].flags==1 && packet.windows[1].flags==1);
  switch(work.ticket.phase){
   case 1:assert(result==0 && fills==f+1 && work.clip.bottom-work.clip.top<=4);++clears;break;
   case 3:assert(result==0 && fills-f<=3);++chrome;break;
   case 4:
    assert(result==6 && fills==f && page_calls==p);++clients;
    /* No implicit callback/ack: the same receipt is offered next poll. */
    struct udeks_repaint_lane_work repeat;assert(repaint_frontend_poll(1,&repeat)==6);
    assert(memcmp(&repeat,&work,sizeof(work))==0 && fills==f && page_calls==p);
    /* Prove common packet clobbering cannot change the local work. */
    memset(&packet,0x69,sizeof(packet));row_client(&work);break;
   case 6:assert(result==0 && page_calls-p<=1);++pages;break;
   default:assert(0);
  }
  assert(page_calls-p<=1 && cx0==0 && cy0==0 && cx1==320 && cy1==200);
 }
 assert(clears==50 && chrome==204 && clients==170 && pages==32 && page_calls==32);
 for(unsigned i=0;i<5;++i)assert(calls[i]==0);
 assert(memcmp(expected,screen,sizeof(screen))==0 && memcmp(expected,display,sizeof(display))==0);
 puts("view packing bounded pixels delegation OK");return 0;
}
'''), b'view packing bounded pixels delegation OK\n')

    def test_fencing_before_edits_stale_slot_and_invalid_geometry(self):
        self.assertEqual(run(r'''
int main(void){
 struct udeks_repaint_rect full={0,320,0,200};struct udeks_repaint_lane_work old,work;
 scene();udeks_vic_bitmap_reset_clip();udeks_lane_init();
 assert(repaint_frontend_control(1,&full,1)==0);
 for(unsigned n=0;;++n){
  assert(n<100 && repaint_frontend_poll(1,&old)==0);
  if(old.ticket.phase==3 && old.ticket.cursor==3)break;
 }
 assert(repaint_frontend_control(2,&full,1)==0); /* BEFORE retiring slot/title. */
 windows[3].title=(const unsigned char *)1;windows[3].z=0;
 unsigned f=fills,p=page_calls;struct udeks_repaint_lane state=udeks_repaint_lane;
 udeks_vic_bitmap_set_clip(111,77,2,3);
 assert(lane_raster_step(&old)==3 && fills==f && page_calls==p);
 assert(memcmp(&state,&udeks_repaint_lane,sizeof(state))==0 && cx0==111 && cy0==77);
 /* Wrap-safe publication guards are independent of host int width. */
 unsigned values[][4]={{65535,0,64,48},{0,0,65535,48},{0,199,48,48},{0,0,15,48},{0,0,48,17},{0,0,48,201}};
 for(unsigned i=0;i<6;++i){
  windows[1].x=values[i][0];windows[1].y=values[i][1];windows[1].width=values[i][2];windows[1].height=values[i][3];
  unsigned c=policy_calls;memset(&work,0x69,sizeof(work));struct udeks_repaint_lane_work before=work;
  assert(repaint_frontend_poll(1,&work)==2 && policy_calls==c && fills==f && page_calls==p);
  assert(memcmp(&before,&work,sizeof(work))==0 && memcmp(&state,&udeks_repaint_lane,sizeof(state))==0);
 }
 assert(repaint_frontend_control(3,0,1)==0 && repaint_receipt_validate(&old.ticket)==3);
 scene();assert(repaint_frontend_poll(1,&work)==1); /* no pending repair after whole-surface abort */
 puts("fence stale slot geometry abort OK");return 0;
}
'''), b'fence stale slot geometry abort OK\n')

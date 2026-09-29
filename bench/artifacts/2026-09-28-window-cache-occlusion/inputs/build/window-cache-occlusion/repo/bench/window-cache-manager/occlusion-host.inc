/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Host pixel oracle: real manager + real lease state, bounded row transport. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned char test_status[32];
SOURCE
volatile unsigned char cache_accept_state=0x80,cache_owner,cache_phase;
struct udeks_cache_geometry manager_test_geometry;
unsigned char manager_test_owner,manager_test_eligible,manager_test_row_offset;
static struct udeks_cache_lease lease;
static unsigned char screen[200][320], image[200][320];
static int cx0,cy0,cx1=320,cy1=200;
static unsigned px=164,py=134,buttons,content;
static unsigned fills,commits,calls[5],paste_requests;

unsigned char cache_accept_poll(void){return 0;}
unsigned char cache_command(unsigned char op){
 unsigned char result=0;
 switch(op){
 case 0:udeks_cache_init(&lease,2224);break;
 case 1:udeks_cache_invalidate(&lease,0);break;
 case 2:result=udeks_cache_capture_begin(&lease,manager_test_owner,1,&manager_test_geometry,manager_test_eligible);break;
 case 3:result=udeks_cache_paste_begin(&lease,manager_test_owner,1,&manager_test_geometry);++paste_requests;break;
 default:assert(0);
 }
 if(!result){cache_owner=lease.owner;cache_phase=lease.phase;}return result;
}
unsigned char cache_step(void){
 struct udeks_cache_row row;
 unsigned char result=udeks_cache_prepare_row(&lease,lease.owner,1,&row);
 if(!result){
   unsigned y=lease.row;
   for(unsigned x=0;x<lease.geometry.width;++x){
     unsigned char *pixel=&screen[lease.geometry.y+y][lease.geometry.x+x];
     if(lease.phase==1)image[y][x]=*pixel;else *pixel=image[y][x];
   }
   manager_test_row_offset=(lease.geometry.y+y)&7;
   result=udeks_cache_commit_row(&lease,lease.owner,1,y);
 }
 if(!result)cache_phase=lease.phase;return result;
}
void udeks_vic_bitmap_set_clip(int x,int y,int w,int h){cx0=x;cy0=y;cx1=x+w;cy1=y+h;}
void udeks_vic_bitmap_reset_clip(void){cx0=cy0=0;cx1=320;cy1=200;}
void udeks_vic_bitmap_commit(void){++commits;}
void udeks_vic_bitmap_pixel(int x,int y,unsigned char c){
 if(x>=0 && x<320 && y>=0 && y<200 && x>=cx0 && x<cx1 && y>=cy0 && y<cy1)screen[y][x]=(c==0);
}
void udeks_vic_bitmap_fill(int x,int y,int w,int h,unsigned char c){
 ++fills;
 for(int yy=y;yy<y+h;++yy)for(int xx=x;xx<x+w;++xx)udeks_vic_bitmap_pixel(xx,yy,c);
}
void udeks_vic_bitmap_line(int x,int y,int xx,int yy,unsigned char c){
 int dx=xx>x?xx-x:x-xx,sx=x<xx?1:-1,dy=yy>y?y-yy:yy-y,sy=y<yy?1:-1,err=dx+dy;
 for(;;){udeks_vic_bitmap_pixel(x,y,c);if(x==xx && y==yy)break;
   int e=2*err;if(e>=dy){err+=dy;x+=sx;}if(e<=dx){err+=dx;y+=sy;}}
}
void udeks_vic_bitmap_rectangle(int x,int y,int w,int h,unsigned char c){
 udeks_vic_bitmap_line(x,y,x+w-1,y,c);udeks_vic_bitmap_line(x,y+h-1,x+w-1,y+h-1,c);
 udeks_vic_bitmap_line(x,y,x,y+h-1,c);udeks_vic_bitmap_line(x+w-1,y,x+w-1,y+h-1,c);
}
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
static void paint(unsigned char h){
 struct udeks_window *w=window_by_handle(h);++calls[h];
 for(unsigned y=w->y;y<w->y+w->height;++y)for(unsigned x=w->x;x<w->x+w->width;++x)
   if((x*3+y*5+(w->owner==1?content:0))%7<3)udeks_vic_bitmap_pixel(x,y,0);
}
static void drive(void){
 unsigned polls=0;
 while(cache_phase==1 || cache_phase==3){udeks_window_manager_poll();assert(++polls<100);}
 assert(cache_phase==2);
}
static void dump(void){fwrite(screen,1,sizeof(screen),stdout);}
int main(void){
 /* Cross >255 X, edge touching, fully hidden, upper-strip and complex fallback.
  * All pixels (including chrome and neighboring shared bytes) match the
  * original tiled compositor after every request and after uncovering. */
 for(unsigned x=0;x<=152;x+=19)for(unsigned y=0;y<=96;y+=8){
   memset(screen,0,sizeof(screen));content=0;udeks_cache_init(&lease,2224);udeks_window_manager_start();
   unsigned lower=udeks_window_create(1,1,15,124,61,72,77,(const unsigned char *)"LOWER",paint,0);
   unsigned top=udeks_window_create(2,1,15,x,y,168,104,(const unsigned char *)"UPPER",paint,0);
   assert(lower==1 && top==2);udeks_window_image_complete(top);drive();dump();
   for(content=1;content<4;++content){
     unsigned old_paste=paste_requests,old_calls=calls[top],lower_calls=calls[lower];
     udeks_window_repaint(lower);
     if(cache_phase==3)drive();
     assert(cache_phase==2 && cache_owner==top && calls[top]==old_calls);
     assert(calls[lower]==lower_calls+1); /* Hidden client acknowledges once. */
     if(OPTIMIZED && x<=124 && x+168>=196 && y+104>=138)
       assert(paste_requests==old_paste);
     dump();
   }
   udeks_window_destroy(top);assert(cache_phase==0);dump();
   udeks_window_manager_reset();
 }
 /* A fourth/high-X window verifies 16-bit damage coordinates, and a middle
  * layer must still be painted in order on the retained upper-strip path. */
 memset(screen,0,sizeof(screen));content=0;udeks_cache_init(&lease,2224);udeks_window_manager_start();
 unsigned disjoint=udeks_window_create(1,1,15,260,60,56,70,0,paint,0);
 unsigned cached=udeks_window_create(2,1,15,0,0,168,104,0,paint,0);
 udeks_window_image_complete(cached);drive();unsigned prior=paste_requests;
 content=2;udeks_window_repaint(disjoint);if(cache_phase==3)drive();dump();
 if(OPTIMIZED)assert(paste_requests==prior);
 udeks_window_manager_reset();memset(screen,0,sizeof(screen));content=0;
 unsigned lower=udeks_window_create(1,1,15,260,60,56,70,0,paint,0);
 udeks_window_create(3,1,15,255,70,60,70,0,paint,0);
 unsigned top=udeks_window_create(2,1,15,152,65,168,104,0,paint,0);
 udeks_window_image_complete(top);drive();content=2;udeks_window_repaint(lower);if(cache_phase==3)drive();dump();
 udeks_window_destroy(top);dump();
 return 0;
}

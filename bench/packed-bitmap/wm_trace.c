/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Binary trace of real 6502 manager state and every drawing/transport call.
 * Drawing is a trace stub, not a raster/pixel or real-input latency proof. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "udeks/window.h"
#include "udeks/window_service.h"
#include "udeks/vic_graphics.h"
#include "udeks/window_cache_state.h"

extern unsigned char test_status[32];
extern unsigned char _HIGHBSS_RUN__[],_HIGHBSS_SIZE__[];
volatile unsigned char cache_accept_state=0x80,cache_owner,cache_phase;
struct udeks_cache_geometry manager_test_geometry;
unsigned char manager_test_owner,manager_test_eligible,manager_test_row_offset;
unsigned char manager_partial_first,manager_partial_end;
unsigned int manager_partial_width;
static struct udeks_cache_lease lease;
static unsigned char partial_end;
static unsigned int px=20;
static unsigned char py=50,buttons;

static void word(unsigned int value)
{
    unsigned char bytes[2];
    bytes[0]=value;bytes[1]=value>>8;
    assert(fwrite(bytes,1,2,stdout)==2);
}
static void draw(unsigned char op,int a,int b,int c,int d,unsigned char e)
{
    word(op);word(a);word(b);word(c);word(d);word(e);
}
unsigned char cache_accept_poll(void) { return 0; }
unsigned char __fastcall__ cache_command(unsigned char op)
{
    unsigned char result=0;
    word(30);word(op);
    switch(op) {
    case 0: udeks_cache_init(&lease,2224);break;
    case 1: udeks_cache_invalidate(&lease,0);break;
    case 2:
        result=udeks_cache_capture_begin(&lease,manager_test_owner,1,
            &manager_test_geometry,manager_test_eligible);break;
    case 3: case 6:
        result=udeks_cache_paste_begin(&lease,manager_test_owner,1,&manager_test_geometry);
        if(!result && op==6) {
            lease.row=manager_partial_first;partial_end=manager_partial_end;
        } else partial_end=0;
        break;
    default: assert(0);
    }
    if(!result) {cache_owner=lease.owner;cache_phase=lease.phase;}
    word(result);return result;
}
unsigned char cache_step(void)
{
    struct udeks_cache_row row;
    unsigned char result;
    result=udeks_cache_prepare_row(&lease,lease.owner,1,&row);
    word(31);word(result);
    if(!result) {
        word(row.shadow_offset);word(row.image_offset);word(row.raw_count);
        manager_test_row_offset=(lease.geometry.y+lease.row)&7;
        result=udeks_cache_commit_row(&lease,lease.owner,1,lease.row);
        if(partial_end && lease.row==partial_end) {lease.phase=2;partial_end=0;}
    }
    if(!result) cache_phase=lease.phase;
    return result;
}
void udeks_vic_bitmap_set_clip(int x,int y,int w,int h) {draw(1,x,y,w,h,0);}
void udeks_vic_bitmap_reset_clip(void) {word(2);}
void udeks_vic_bitmap_commit(void) {word(3);}
void udeks_vic_bitmap_fill(int x,int y,int w,int h,unsigned char c) {draw(4,x,y,w,h,c);}
void udeks_vic_bitmap_pixel(int x,int y,unsigned char c) {draw(5,x,y,0,0,c);}
void udeks_vic_bitmap_line(int x,int y,int xx,int yy,unsigned char c) {draw(6,x,y,xx,yy,c);}
void udeks_vic_bitmap_rectangle(int x,int y,int w,int h,unsigned char c) {draw(7,x,y,w,h,c);}
void udeks_vic_pointer_busy_begin(unsigned char r) {word(8);word(r);}
void udeks_vic_pointer_busy_end(unsigned char r) {word(9);word(r);}
void udeks_vic_bitmap_outline_toggle(unsigned x,unsigned char y,unsigned w,unsigned char h)
{draw(10,x,y,w,h,0);}
void udeks_vic_bitmap_outline_move(unsigned x,unsigned char y,unsigned xx,unsigned char yy,
    unsigned w,unsigned char h) {draw(11,x,y,xx,yy,h);word(w);}
unsigned char udeks_vic_graphics_is_active(void) {return 1;}
unsigned int udeks_pointer_x(void) {return px;}
unsigned char udeks_pointer_y(void) {return py;}
unsigned char udeks_pointer_buttons(void) {return buttons;}
void udeks_pointer_resynchronize(void) {word(12);}
static void paint(unsigned char h) {word(13);word(h);}
static void closed(unsigned char h) {word(14);word(h);}
static void state(void)
{
    unsigned char h,i,y,height;
    unsigned int x,width;
    const struct udeks_window_click *click;
    for(i=0;i<32;++i) word(test_status[i]);
    for(h=0;h<6;++h) {
        word(udeks_window_owner(h));word(udeks_window_is_focused(h));
        word(udeks_window_is_dragging(h));
        if(!udeks_window_get_geometry(h,&x,&y,&width,&height)) {
            word(x);word(y);word(width);word(height);
        }
        click=udeks_window_take_click(h);
        word(click!=0);if(click) {word(click->x);word(click->y);}
    }
}
static void drive(void)
{
    unsigned char polls=0;
    while(cache_phase==1 || cache_phase==3) {
        word(udeks_window_manager_poll());assert(++polls<100);
    }
    state();
}
static void gesture(unsigned x,unsigned char y,unsigned xx,unsigned char yy)
{
    px=x+12;py=y+40;buttons=0;udeks_window_manager_poll();
    buttons=1;udeks_window_manager_poll();state();
    px=xx+12;py=yy+40;udeks_window_manager_poll();state();
    buttons=0;udeks_window_manager_poll();drive();
}
int main(void)
{
    unsigned int width;
    unsigned char h,i;
    memset(_HIGHBSS_RUN__,0,(unsigned int)_HIGHBSS_SIZE__);
    udeks_cache_init(&lease,2224);udeks_window_manager_start();
    for(width=16;width<=320;width+=16) {
        h=udeks_window_create(1,1,15,320-width,10,width,90,
            (const unsigned char *)"aZ! TEST",paint,closed);
        assert(h==1);state();
        word(udeks_window_image_complete(h));drive();
        word(udeks_window_repaint(h));drive();
        word(udeks_window_destroy(h));state();
    }
    for(i=0;i<4;++i) assert(udeks_window_create(i+1,1,15,
        (unsigned int)i*74,10+i*24,72,72,(const unsigned char *)"TEST",paint,closed)==i+1);
    assert(!udeks_window_create(9,1,15,0,0,72,72,0,paint,closed));state();
    word(udeks_window_image_complete(4));drive();
    gesture(230,87,241,94); /* cached drag, including X>255 clip arithmetic */
    gesture(268,128,268,128); /* client click */
    gesture(300,154,270,170); /* resize */
    for(h=1;h<5;++h) {word(udeks_window_repaint(h));drive();}
    for(h=1;h<5;++h) {word(udeks_window_destroy(h));state();}
    word(udeks_window_manager_stop());state();
    return 0;
}

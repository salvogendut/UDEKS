/* SPDX-License-Identifier: GPL-3.0-or-later */
#define UDEKS_GRAPHICS_HOST_TEST
unsigned char graphics_request[38], graphics_memory[65536];
unsigned char graphics_overlay[1008], graphics_pool[2304];
unsigned char udeks_shell_foreground_job, graphics_foreground_exit, test_exit[4];
const unsigned char udeks_native_base_pages[4]={0x23,0x35,0x80,0xc6};
const unsigned char udeks_native_stack_pages[4]={0x34,0x3f,0x8f,0xcf};
#include "../../src/services/window/banked_graphics.c"
#undef R
#undef P
#undef C
#include "../../src/services/window/retained_paths.c"

unsigned char test_task, test_state[4], test_reap_busy, test_owner[5];
unsigned char test_load_error, test_activate_error, test_selector, test_path[17];
unsigned char test_active, test_init_calls, test_init_error;
unsigned int test_repaints, test_writes, test_draws, test_x, test_y;
int test_lines[2048][4];
int test_fills[2048][5];
static udeks_window_paint_fn painter[5];
static udeks_window_close_fn closer[5];
static struct udeks_window_click pending;
static unsigned char click_handle;
static unsigned int origin_x;
static unsigned char origin_y;
static unsigned int widths[5];
static unsigned char heights[5];
unsigned char test_flags[5];
unsigned char test_dragging;
unsigned char test_busy, test_background;
unsigned char input_pointer[32], test_focused;
unsigned int test_begin_paints, test_end_paints;
unsigned char udeks_window_is_dragging(unsigned char h) { return test_dragging==h; }
unsigned char udeks_window_update_busy(void) { return test_busy || test_dragging; }
unsigned char udeks_window_is_focused(unsigned char h) { return h==test_focused; }
void udeks_graphics_geometry(unsigned char h) {
    udeks_window_get_geometry(h,&udeks_graphics_origin_x,&udeks_graphics_origin_y,
        &udeks_graphics_width,&udeks_graphics_height);
}
#include "../../bench/graphics-input/reference.h"
unsigned char udeks_window_begin_paint(unsigned char h) {
    (void)h; ++test_begin_paints; return test_background;
}
void udeks_window_end_paint(void) { ++test_end_paints; }

void test_reset(void)
{
    udeks_shell_foreground_job=graphics_foreground_exit=0;
    memset(test_exit,0,sizeof(test_exit));
    memset(&clients,0,sizeof(clients));
    memset(running,0,sizeof(running));
    memset(udeks_retained_lengths,0,sizeof(udeks_retained_lengths));
    memset(graphics_overlay,0,sizeof(graphics_overlay));
    memset(graphics_pool,0,sizeof(graphics_pool));
    memset(udeks_banked_graphics_names,0,sizeof(udeks_banked_graphics_names));
    memset(graphics_request,0,sizeof(graphics_request));
    memset(graphics_memory,0,sizeof(graphics_memory));
    memset(test_owner,0,sizeof(test_owner));
    memset(widths,0,sizeof(widths));memset(heights,0,sizeof(heights));
    udeks_banked_graphics_installed=0;
    test_task=3; memset(test_state,0,sizeof(test_state)); test_reap_busy=0;
    test_repaints=test_writes=test_draws=0; click_handle=test_dragging=0;
    test_busy=test_background=0; test_begin_paints=test_end_paints=0;
    test_focused=0;memset(input_pointer,0,sizeof(input_pointer));
    test_load_error=test_activate_error=test_selector=0;
    test_active=test_init_calls=test_init_error=0;
    memset(test_path,0,sizeof(test_path));
    origin_x=100; origin_y=20;
}
void test_admit(unsigned char index) { running[index]=1; test_state[index]=4; }
unsigned char udeks_vic_graphics_is_active(void) { return test_active; }
unsigned char udeks_vic_graphics_initialize(void) {
    ++test_init_calls;
    if(!test_init_error) test_active=1;
    return test_init_error;
}
unsigned char udeks_banked_call(unsigned char selector)
{
    unsigned char i;
    if(!selector) {
        if(test_load_error) return test_load_error;
        for(i=0;i<4;++i) if(!test_state[i]) {
            test_selector=i+3; memcpy(test_path,P,17);
            if(test_activate_error) return test_activate_error;
            test_state[i]=1; R[11]=i+3; return 0;
        }
        return 16;
    }
    if(selector==0x30) return test_task;
    if(selector>=0x63 && selector<=0x66) {
        R[11]=test_exit[selector-0x63]; return test_state[selector-0x63];
    }
    if(selector>=0xc3 && selector<=0xc6) {
        if(!test_reap_busy) test_state[selector-0xc3]=0;
        return test_reap_busy;
    }
    if(selector>=3 && selector<=6) {
        test_selector=selector; memcpy(test_path,P,17); return test_load_error;
    }
    if(selector>=0x43 && selector<=0x46) return test_activate_error;
    return 0;
}
/* Host equivalent of the bounded assembly request-marshalling adapter. */
unsigned char udeks_banked_graphics_exec(const unsigned char *name)
{
    unsigned char n=0;
    while(name[n] && n<16) { P[n+1]=name[n]; ++n; }
    if(name[n]) return 5;
    P[0]=n;
    while(n<16) P[++n]=0;
    R[10]=17;
    return udeks_banked_graphics_launch();
}
void udeks_banked_read(unsigned int address) {
    P[0]=address&255; P[1]=address>>8;
    memcpy(C,graphics_memory+address,8);
}
void udeks_banked_write(unsigned int address) {
    P[0]=address&255; P[1]=address>>8;
    memcpy(graphics_memory+address,C,8); ++test_writes;
}
unsigned char udeks_window_owner(unsigned char h) { return h<5?test_owner[h]:0; }
unsigned char udeks_window_create(unsigned char owner,unsigned char surface,unsigned char flags,
    unsigned int x,unsigned char y,unsigned int width,unsigned char height,
    const unsigned char *title,udeks_window_paint_fn paint_fn,udeks_window_close_fn close_fn)
{
    unsigned char h=owner-0x82;
    (void)surface;(void)x;(void)y;(void)title;
    if(!width || !height || h>4) return 0;
    test_owner[h]=owner; painter[h]=paint_fn;closer[h]=close_fn;
    test_focused=h;
    widths[h]=width;heights[h]=height;test_flags[h]=flags;
    return h;
}
unsigned char udeks_window_destroy(unsigned char h)
{
    test_owner[h]=0; closer[h](h); return 0;
}
unsigned char udeks_window_repaint(unsigned char h)
{
    ++test_repaints; painter[h](h); return 0;
}
unsigned char udeks_window_get_geometry(unsigned char h,unsigned int *x,unsigned char *y,
    unsigned int *w,unsigned char *height)
{
    *x=origin_x;*y=origin_y;*w=widths[h];*height=heights[h];return 0;
}
const struct udeks_window_click *udeks_window_take_click(unsigned char h)
{
    if(test_dragging) return 0;
    if(click_handle!=h) return 0;
    click_handle=0;return &pending;
}
void test_click(unsigned char h,unsigned int x,unsigned char y)
{
    click_handle=h;pending.x=x;pending.y=y;
}
void test_move(unsigned char h,unsigned int x,unsigned char y)
{
    origin_x=x;origin_y=y;udeks_window_repaint(h);
}
void test_resize(unsigned char h,unsigned int w,unsigned char height)
{
    widths[h]=w;heights[h]=height;
}
void udeks_vic_bitmap_fill(int x,int y,int w,int h,unsigned char color)
{
    if(test_draws<2048) {
        test_fills[test_draws][0]=x;test_fills[test_draws][1]=y;
        test_fills[test_draws][2]=w;test_fills[test_draws][3]=h;
        test_fills[test_draws][4]=color;
    }
    test_x=x;test_y=y;++test_draws;
}
void udeks_vic_bitmap_line(int x,int y,int x2,int y2,unsigned char color)
{
    if(test_draws<2048) {
        test_lines[test_draws][0]=x;test_lines[test_draws][1]=y;
        test_lines[test_draws][2]=x2;test_lines[test_draws][3]=y2;
    }
    udeks_vic_bitmap_fill(x,y,0,0,color);
}

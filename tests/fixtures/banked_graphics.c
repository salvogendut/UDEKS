/* SPDX-License-Identifier: GPL-3.0-or-later */
#define UDEKS_GRAPHICS_HOST_TEST
unsigned char graphics_request[38], graphics_memory[65536];
#include "../../src/services/window/banked_graphics.c"

unsigned char test_task, test_state[2], test_reap_busy, test_owner[5];
unsigned char test_load_error, test_activate_error, test_selector, test_path[17];
unsigned char test_active, test_init_calls, test_init_error;
unsigned int test_repaints, test_writes, test_draws, test_x, test_y;
static udeks_window_paint_fn painter[5];
static udeks_window_close_fn closer[5];
static struct udeks_window_click pending;
static unsigned char click_handle;
static unsigned int origin_x;
static unsigned char origin_y;

void test_reset(void)
{
    memset(&clients,0,sizeof(clients));
    memset(udeks_banked_graphics_names,0,sizeof(udeks_banked_graphics_names));
    memset(graphics_request,0,sizeof(graphics_request));
    memset(graphics_memory,0,sizeof(graphics_memory));
    memset(test_owner,0,sizeof(test_owner));
    udeks_banked_graphics_installed=0;
    test_task=3; test_state[0]=test_state[1]=0; test_reap_busy=0;
    test_repaints=test_writes=test_draws=0; click_handle=0;
    test_load_error=test_activate_error=test_selector=0;
    test_active=test_init_calls=test_init_error=0;
    memset(test_path,0,sizeof(test_path));
    origin_x=100; origin_y=20;
}
void test_admit(unsigned char index) { clients.running[index]=1; test_state[index]=4; }
unsigned char udeks_vic_graphics_is_active(void) { return test_active; }
unsigned char udeks_vic_graphics_initialize(void) {
    ++test_init_calls;
    if(!test_init_error) test_active=1;
    return test_init_error;
}
unsigned char udeks_banked_call(unsigned char selector)
{
    unsigned char i, first=0, limit=2;
    if(!selector) {
        if(test_load_error) return test_load_error;
        if(!memcmp(P+1,"xcalc",5)) limit=1;
        if(!memcmp(P+1,"xdraw",5)) first=1;
        for(i=first;i<limit;++i) if(!test_state[i]) {
            test_selector=i+3; memcpy(test_path,P,17);
            if(test_activate_error) return test_activate_error;
            test_state[i]=1; R[11]=i+3; return 0;
        }
        return 16;
    }
    if(selector==0x30) return test_task;
    if(selector==0x63 || selector==0x64) return test_state[selector-0x63];
    if(selector==0xc3 || selector==0xc4) {
        if(!test_reap_busy) test_state[selector-0xc3]=0;
        return test_reap_busy;
    }
    if(selector==3 || selector==4) {
        test_selector=selector; memcpy(test_path,P,17); return test_load_error;
    }
    if(selector==0x43 || selector==0x44) return test_activate_error;
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
void udeks_banked_read(unsigned int address) { memcpy(C,graphics_memory+address,8); }
void udeks_banked_write(unsigned int address) { memcpy(graphics_memory+address,C,8); ++test_writes; }
unsigned char udeks_window_owner(unsigned char h) { return h<5?test_owner[h]:0; }
unsigned char udeks_window_create(unsigned char owner,unsigned char surface,unsigned char flags,
    unsigned int x,unsigned char y,unsigned int width,unsigned char height,
    const unsigned char *title,udeks_window_paint_fn paint_fn,udeks_window_close_fn close_fn)
{
    unsigned char h=owner-0x82;
    (void)surface;(void)flags;(void)x;(void)y;(void)title;
    if(!width || !height || h>4) return 0;
    test_owner[h]=owner; painter[h]=paint_fn;closer[h]=close_fn;
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
    (void)h;*x=origin_x;*y=origin_y;*w=104;*height=133;return 0;
}
const struct udeks_window_click *udeks_window_take_click(unsigned char h)
{
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
void udeks_vic_bitmap_fill(int x,int y,int w,int h,unsigned char color)
{
    (void)w;(void)h;(void)color;test_x=x;test_y=y;++test_draws;
}
void udeks_vic_bitmap_line(int x,int y,int x2,int y2,unsigned char color)
{
    (void)x2;(void)y2;udeks_vic_bitmap_fill(x,y,0,0,color);
}

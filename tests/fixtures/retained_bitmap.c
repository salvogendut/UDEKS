/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Real legacy allocator and new fixed-pool handler, no fake allocation logic. */
#include <string.h>
#define UDEKS_GRAPHICS_HOST_TEST
unsigned char graphics_request[38],graphics_pool[2304];
unsigned int udeks_retained_lengths[4],udeks_graphics_origin_x;
unsigned char udeks_graphics_origin_y;
unsigned char bitmap_canvas[64000];
unsigned int bitmap_clip_left,bitmap_clip_top,bitmap_clip_right=320,bitmap_clip_bottom=200;
const unsigned char udeks_native_base_pages[4]={0x23,0x35,0x80,0xc6};
const unsigned char udeks_native_stack_pages[4]={0x34,0x3f,0x8f,0xcf};
void udeks_banked_read(unsigned int address) { (void)address; }
void udeks_vic_bitmap_line(int x,int y,int xx,int yy,unsigned char c)
{ (void)x;(void)y;(void)xx;(void)yy;(void)c; }
void udeks_vic_bitmap_pixel(int x,int y,unsigned char color)
{
    if(x>=0 && x<320 && y>=0 && y<200 && (unsigned)x>=bitmap_clip_left && (unsigned)x<bitmap_clip_right &&
       (unsigned)y>=bitmap_clip_top && (unsigned)y<bitmap_clip_bottom) bitmap_canvas[y*320+x]=(color==0);
}
#include "../../src/services/window/retained_paths.c"
#undef P
#include "../../src/services/window/retained_bitmap.c"

void bitmap_reset(void)
{
    memset(graphics_pool,0xa5,sizeof(graphics_pool));
    memset(udeks_retained_lengths,0,sizeof(udeks_retained_lengths));
    memset(graphics_request,0,sizeof(graphics_request));
    memset(bitmap_canvas,0,sizeof(bitmap_canvas));
    udeks_graphics_origin_x=udeks_graphics_origin_y=0;
    bitmap_clip_left=bitmap_clip_top=0;bitmap_clip_right=320;bitmap_clip_bottom=200;
}
unsigned char bitmap_request(unsigned char index,const unsigned char *request)
{
    memcpy(graphics_request+14,request,24);
    return udeks_retained_bitmap_request(index);
}
void bitmap_discard(unsigned char index)
{
    if(index<4) udeks_retained_discard(index);
}

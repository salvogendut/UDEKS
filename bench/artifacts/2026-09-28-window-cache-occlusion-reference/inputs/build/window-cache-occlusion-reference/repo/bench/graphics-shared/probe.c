/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/vic_graphics.h"
#include "udeks/memory.h"
#define RESULT ((volatile unsigned char *)0x7FC0u)
#define ROWS ((unsigned int *)UDEKS_VIC_ROW_TABLE_BASE)
#define DIRTY ((unsigned char *)UDEKS_VIC_DIRTY_MAP_BASE)
#define CLIP ((int *)UDEKS_VIC_CLIP_STATE_BASE)
extern unsigned char udeks_vic_bitmap_shadow[8000];
extern void raster_timer_start(void), raster_timer_stop(void);
extern unsigned int pixel_probe_sp(void);
static unsigned int initial_sp, final_sp;
static unsigned char failed;
#if CASE <= 2
static void checked_line(int x, int y, int xx, int yy, unsigned char color)
{
    unsigned int before, after;
    before = pixel_probe_sp();
    udeks_vic_bitmap_line(x, y, xx, yy, color);
    after = pixel_probe_sp();
    if (before != after) failed = 1;
}
#elif CASE == 3
static void checked_rect(int x, int y, int w, int h, unsigned char color)
{
    unsigned int before, after;
    before = pixel_probe_sp();
    udeks_vic_bitmap_rectangle(x, y, w, h, color);
    after = pixel_probe_sp();
    if (before != after) failed = 1;
}
#endif

int main(void)
{
    unsigned int i;
#if CASE <= 3
    unsigned char n;
#endif
#if CASE == 0 || CASE == 2
    int x, y;
#endif
#if CASE == 2
    unsigned char a, b;
    static const int xs[8] = {-20, 0, 1, 7, 8, 159, 319, 340};
    static const int ys[8] = {-15, 0, 1, 7, 8, 99, 199, 215};
#endif
    for (i = 0; i < 64u; ++i) RESULT[i] = 0;
    RESULT[0]='S'; RESULT[1]='H'; RESULT[2]='R'; RESULT[3]='D';
    RESULT[4]=1; RESULT[5]=1; RESULT[6]=VARIANT; RESULT[7]=CASE;
    initial_sp = pixel_probe_sp();
    for (i=0; i<200u; ++i) ROWS[i]=(i&248u)*40u+(i&7u);
    for (i=0; i<8000u; ++i) udeks_vic_bitmap_shadow[i]=(unsigned char)(i*13u+7u);
    for (i=0; i<32u; ++i) DIRTY[i]=0;
#if CASE == 3
    CLIP[0]=49; CLIP[1]=25; CLIP[2]=271; CLIP[3]=167;
#else
    CLIP[0]=0; CLIP[1]=0; CLIP[2]=320; CLIP[3]=200;
#endif
    *(volatile unsigned char *)0xA1DFu=0x5Au;
    *(volatile unsigned char *)0xC120u=0xA5u;
    *(volatile unsigned char *)0xE1B8u=0xC3u;
    failed=0;
    raster_timer_start();
#if CASE == 0
    for (n=0; n<96u; ++n) {
        x=(n%24u)*11u+10u; y=(n%16u)*9u+10u;
        checked_line(x,y,x+17,y+11,n&1u);
    }
#elif CASE == 1
    for (n=0; n<24u; ++n)
        checked_line(-20,n*7u,340,190-(int)n*6,n&1u);
#elif CASE == 2
    for (a=0; a<8u; ++a) for (b=0; b<8u; ++b) {
        x=xs[a]; y=ys[b]; n=(a+b)&1u;
        checked_line(x,y,319-x,199-y,n);
        checked_line(x,y,x,y,7);
        checked_line(159,99,x,y,n);
        checked_line(x,y,159,99,n);
    }
    /* All eight directed octants plus the axes and degenerate point. */
    for (a=0; a<8u; ++a) {
        checked_line(160,100,xs[a],100,0);
        checked_line(160,100,160,ys[a],255);
    }
#elif CASE == 3
    for (n=0; n<64u; ++n) {
        checked_rect(40+(n&7u),20+(n>>3),19+(n>>3),11+(n&7u),n&1u);
        checked_rect(260+(n&7u),155+(n>>3),1,1+(n&7u),7);
    }
    checked_rect(-10,-8,350,230,0);
    checked_rect(49,25,222,142,255);
    checked_rect(51,27,1,1,0);
    checked_rect(52,28,1,30,0);
    checked_rect(53,29,30,1,0);
    checked_rect(50,26,0,20,0);
    checked_rect(50,26,20,-1,0);
    checked_rect(320,200,10,10,0);
    checked_rect(-20,-20,10,10,0);
#elif CASE == 4
    /* Whole-surface clear deliberately ignores a small clip. */
    CLIP[0]=49; CLIP[1]=25; CLIP[2]=271; CLIP[3]=167;
    udeks_vic_bitmap_clear(0);
#elif CASE == 5
    udeks_vic_bitmap_clear(255);
#endif
    raster_timer_stop();
    final_sp = pixel_probe_sp();
    if (initial_sp != final_sp) failed=1;
    RESULT[12]=*(volatile unsigned char *)0xA1DFu;
    RESULT[13]=*(volatile unsigned char *)0xC120u;
    RESULT[14]=*(volatile unsigned char *)0xE1B8u;
    RESULT[15]=failed;
    for (i=0; i<8000u; ++i) RESULT[64u+i]=udeks_vic_bitmap_shadow[i];
    for (i=0; i<32u; ++i) RESULT[8064u+i]=DIRTY[i];
    RESULT[5]=2;
    return 0;
}

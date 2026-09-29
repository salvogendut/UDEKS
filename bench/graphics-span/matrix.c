/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/vic_graphics.h"
#include "udeks/memory.h"
#define RESULT ((volatile unsigned char *)0x7FC0u)
#define ROWS ((unsigned int *)UDEKS_VIC_ROW_TABLE_BASE)
#define DIRTY ((unsigned char *)UDEKS_VIC_DIRTY_MAP_BASE)
#define CLIP ((int *)UDEKS_VIC_CLIP_STATE_BASE)
extern unsigned char udeks_vic_bitmap_shadow[8000];
extern void raster_timer_start(void), raster_timer_stop(void);

int main(void)
{
    unsigned int i;
#if CASE != 5
    unsigned char a, b, color, width;
#endif
    for (i = 0; i < 64u; ++i) RESULT[i] = 0;
    RESULT[0]='R'; RESULT[1]='A'; RESULT[2]='S'; RESULT[3]='T';
    RESULT[4]=1; RESULT[5]=1; RESULT[6]=VARIANT; RESULT[7]=CASE;
    for (i = 0; i < 200u; ++i) ROWS[i]=(i & 248u)*40u+(i & 7u);
    for (i = 0; i < 8000u; ++i) udeks_vic_bitmap_shadow[i]=(unsigned char)(i*13u+7u);
    for (i = 0; i < 32u; ++i) DIRTY[i]=0;
    CLIP[0]=0; CLIP[1]=0; CLIP[2]=320; CLIP[3]=200;
    *(volatile unsigned char *)0xA1DFu=0x5Au;
    *(volatile unsigned char *)0xC120u=0xA5u;
    *(volatile unsigned char *)0xE1B8u=0xC3u;
    raster_timer_start();
#if CASE == 5
    /* Fresh dirty map: logical page 0 -> 1, physical address $A1E6 -> $A31E.
     * Later matrix rows must not hide a missing initial or crossing flag. */
    udeks_vic_bitmap_fill(0,6,320,1,0);
#else
    /* Each color has distinct rows: all 64 first/last alignment pairs. */
    for (color=0; color<2u; ++color)
        for (a=0; a<8u; ++a)
            for (b=0; b<8u; ++b)
                udeks_vic_bitmap_fill(a, color*64u+a*8u+b, 17u+b-a, 1, color);
    /* Every nonempty single-byte edge-mask intersection. */
    for (a=0; a<8u; ++a)
        for (width=1; width<=8u-a; ++width) {
            udeks_vic_bitmap_fill(a, 128u+a*8u+width-1u, width, 1, 0);
            udeks_vic_bitmap_fill(312u+a, 128u+a*8u+width-1u, width, 1, 7);
        }
    udeks_vic_bitmap_fill(0,192,320,1,0);
    udeks_vic_bitmap_fill(0,193,320,1,255);
    udeks_vic_bitmap_fill(319,199,1,1,0);
    udeks_vic_bitmap_fill(0,198,1,1,7);
    udeks_vic_bitmap_fill(-3,-2,12,5,0);
    udeks_vic_bitmap_fill(318,198,10,10,7);
    udeks_vic_bitmap_fill(10,10,0,10,0);
    udeks_vic_bitmap_fill(10,10,10,-1,0);
    udeks_vic_bitmap_fill(320,0,10,10,0);
    udeks_vic_bitmap_fill(0,200,10,10,0);
#endif
    raster_timer_stop();
    RESULT[12]=*(volatile unsigned char *)0xA1DFu;
    RESULT[13]=*(volatile unsigned char *)0xC120u;
    RESULT[14]=*(volatile unsigned char *)0xE1B8u;
    for (i=0; i<8000u; ++i) RESULT[64u+i]=udeks_vic_bitmap_shadow[i];
    for (i=0; i<32u; ++i) RESULT[8064u+i]=DIRTY[i];
    RESULT[5]=2;
    return 0;
}

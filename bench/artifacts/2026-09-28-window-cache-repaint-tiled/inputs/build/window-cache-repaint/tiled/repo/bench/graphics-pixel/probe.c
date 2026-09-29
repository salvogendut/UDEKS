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
static unsigned int initial_sp;
static unsigned int final_sp;
static unsigned char failed;

#if CASE != 3
static void checked_pixel(int x, int y, unsigned char color)
{
    unsigned int before, after;
    before = pixel_probe_sp();
    udeks_vic_bitmap_pixel(x,y,color);
    /* Read before comparing: cc65 may push the left comparison operand. */
    after = pixel_probe_sp();
    if (before != after) failed=1;
}
#endif

int main(void)
{
    unsigned int i;
#if CASE == 1 || CASE == 3
    int x,y;
#endif
#if CASE == 0
    unsigned char a,b,color;
#endif
    for (i=0;i<64u;++i) RESULT[i]=0;
    RESULT[0]='P';RESULT[1]='I';RESULT[2]='X';RESULT[3]='L';
    RESULT[4]=1;RESULT[5]=1;RESULT[6]=VARIANT;RESULT[7]=CASE;
    initial_sp=pixel_probe_sp();
    for(i=0;i<200u;++i)ROWS[i]=(i&248u)*40u+(i&7u);
    for(i=0;i<8000u;++i)udeks_vic_bitmap_shadow[i]=(unsigned char)(i*13u+7u);
    for(i=0;i<32u;++i)DIRTY[i]=0;
    CLIP[0]=0;CLIP[1]=0;CLIP[2]=320;CLIP[3]=200;
    *(volatile unsigned char *)0xA1DFu=0x5Au;
    *(volatile unsigned char *)0xC120u=0xA5u;
    *(volatile unsigned char *)0xE1B8u=0xC3u;
    failed=0;
    raster_timer_start();
#if CASE == 0
    for(color=0;color<2u;++color)
        for(a=0;a<8u;++a)
            for(b=0;b<8u;++b)
                checked_pixel(8+a,color*64u+a*8u+b,color);
    for(i=0;i<200u;++i)checked_pixel(319,(int)i,7);
    checked_pixel(0,0,0);checked_pixel(0,199,255);
#elif CASE == 1
    CLIP[0]=49;CLIP[1]=25;CLIP[2]=271;CLIP[3]=167;
    for(y=24;y<=167;++y) {
        checked_pixel(48,y,0);checked_pixel(49,y,0);
        checked_pixel(270,y,7);checked_pixel(271,y,7);
    }
    for(x=48;x<=271;++x) {
        checked_pixel(x,24,0);checked_pixel(x,25,0);
        checked_pixel(x,166,255);checked_pixel(x,167,255);
    }
    checked_pixel(-32767-1,30,0);checked_pixel(32767,30,0);
    checked_pixel(60,-32767-1,0);checked_pixel(60,32767,0);
    checked_pixel(-1,30,0);checked_pixel(60,-1,0);
    CLIP[0]=5000;CLIP[2]=5000; /* empty clip, outside physical screen */
    checked_pixel(5000,30,0);checked_pixel(60,30,0);
    CLIP[0]=0;CLIP[2]=320;CLIP[1]=5000;CLIP[3]=5000;
    checked_pixel(60,5000,0);checked_pixel(60,30,0);
#elif CASE == 2
    /* Two pixels straddle logical page 0/1, but not the same physical boundary. */
    checked_pixel(240,0,0);checked_pixel(261,0,255);
#elif CASE == 3
    for(i=0;i<1024u;++i) {
        x=(int)((i*37u)%320u);y=(int)((i*17u)%200u);
        udeks_vic_bitmap_pixel(x,y,(unsigned char)(i&1u));
    }
#endif
    raster_timer_stop();
    final_sp=pixel_probe_sp();
    if(initial_sp!=final_sp)failed=1;
    RESULT[12]=*(volatile unsigned char *)0xA1DFu;
    RESULT[13]=*(volatile unsigned char *)0xC120u;
    RESULT[14]=*(volatile unsigned char *)0xE1B8u;
    RESULT[15]=failed;
    for(i=0;i<8000u;++i)RESULT[64u+i]=udeks_vic_bitmap_shadow[i];
    for(i=0;i<32u;++i)RESULT[8064u+i]=DIRTY[i];
    RESULT[5]=2;
    return 0;
}

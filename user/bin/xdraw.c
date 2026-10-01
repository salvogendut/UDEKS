/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent task-4 disk client: click cells to toggle ink, C to clear. */
#include "udeks/banked_graphics.h"
#define R ((volatile unsigned char *)0xf359)
#define P ((volatile unsigned char *)0xf367)
extern unsigned char __fastcall__ gfx_request(unsigned char op);
extern void gfx_sleep(void);
unsigned char udeks_xdraw_cells[24];
static unsigned char commands[41][8], count, handle;

static void shape(unsigned char op, unsigned char x, unsigned char y,
    unsigned char a, unsigned char b)
{
    commands[count][0]=op; commands[count][1]=x; commands[count][2]=y;
    commands[count][3]=a; commands[count][4]=b; commands[count][5]=0;
    ++count;
}
static void payload(void)
{
    unsigned char i;
    for(i=0;i<24;++i) P[i]=0;
    P[1]=handle;
}
static unsigned char present(void)
{
    unsigned char i;
    count=0;
    for(i=0;i<7;++i) shape(1,2+i*16u,16,2+i*16u,80);
    for(i=0;i<5;++i) shape(1,2,16+i*16u,98,16+i*16u);
    for(i=0;i<24;++i) if(udeks_xdraw_cells[i])
        shape(0,4+(i%6u)*16u,18+(i/6u)*16u,13,13);
    shape(1,2,84,26,84); shape(1,2,100,26,100);
    shape(1,2,84,2,100); shape(1,26,84,26,100);
    shape(2,11,87,3,4);
    commands[count-1][5]=4; commands[count-1][6]=4; commands[count-1][7]=3;
    payload(); P[2]=(unsigned int)commands; P[3]=(unsigned int)commands>>8; P[4]=count;
    return gfx_request(UDEKS_GFX_PRESENT);
}
unsigned char udeks_graphical_main(void)
{
    unsigned char i,x,y;
    payload(); P[1]=216; P[3]=65; P[4]=100; P[5]=103; P[6]=0x16;
    for(i=0;i<5;++i) P[7+i]="XDRAW"[i];
    if(gfx_request(UDEKS_GFX_CREATE)) return 1;
    handle=R[11];
    if(present()) return 2;
    for(;;) {
        payload(); if(gfx_request(UDEKS_GFX_EVENT)) return 3;
        if(!P[0]) return 0;
        if((P[0]&2) && !P[2]) {
            x=P[1]; y=P[3];
            if(x>2 && x<98 && y>16 && y<80) {
                i=((y-16)/16)*6+(x-2)/16;
                udeks_xdraw_cells[i]^=1;
            } else if(x>2 && x<26 && y>84 && y<100) {
                for(i=0;i<24;++i) udeks_xdraw_cells[i]=0;
            } else { gfx_sleep(); continue; }
            if(present()) return 4;
        }
        gfx_sleep();
    }
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Slot-independent example. No task number, load base or resident app ID. */
#include "udeks/banked_graphics.h"
#define R ((volatile unsigned char *)0xf359)
#define P ((volatile unsigned char *)0xf367)
extern unsigned char __fastcall__ gfx_request(unsigned char op);
extern void gfx_sleep(void);
unsigned char hello_clicks;
static unsigned char handle;
static unsigned char commands[3][8]={
    {1,8,20,88,20,0,0,0}, {1,8,40,88,40,0,0,0},
    {0,20,24,12,12,0,0,0}
};

static void payload(void)
{
    unsigned char i;
    for(i=0;i<24;++i) P[i]=0;
    P[1]=handle;
}
static unsigned char present(void)
{
    payload(); P[2]=(unsigned int)commands; P[3]=(unsigned int)commands>>8; P[4]=3;
    return gfx_request(UDEKS_GFX_PRESENT);
}
unsigned char udeks_graphical_main(void)
{
    unsigned char i;
    payload(); P[1]=50; P[3]=40; P[4]=100; P[5]=64; P[6]=0x16;
    for(i=0;i<5;++i) P[i+7]="HELLO"[i];
    if(gfx_request(UDEKS_GFX_CREATE)) return 1;
    handle=R[11];
    if(present()) return 2;
    for(;;) {
        payload(); if(gfx_request(UDEKS_GFX_EVENT)) return 3;
        if(!P[0]) return 0;
        if(P[0]&2) {
            ++hello_clicks;
            commands[2][1]=hello_clicks&1?65:20;
            if(present()) return 4;
        }
        gfx_sleep();
    }
}

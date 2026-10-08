/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent, deliberately large UDEX client. No fixed task/base bindings. */
#include "udeks/banked_graphics.h"
#define R ((volatile unsigned char *)0xf359)
#define P ((volatile unsigned char *)0xf367)
extern unsigned char __fastcall__ gfx_request(unsigned char op);
extern void gfx_sleep(void);

/* Initialized data tests FILE capacity as well as runtime allocation. The
 * commands below reside beyond the ordinary allocation's $3400 stack page. */
#ifdef CAPACITY_CONSOLE
volatile unsigned char capacity_padding[4600];
#define INITIAL_BYTE 0
#else
volatile unsigned char capacity_padding[4600] = {0x5a};
#define INITIAL_BYTE 0x5a
#endif
unsigned char capacity_ready, capacity_error, capacity_control;
unsigned int capacity_progress;
unsigned char commands[3][8];
static unsigned char handle;

static void payload(void)
{
    unsigned char i;
    for(i=0;i<24;++i) P[i]=0;
    P[1]=handle;
}
unsigned char udeks_graphical_main(void)
{
    unsigned int i;
    /* Both initialized DATA and zeroed BSS must survive relocation/install. */
    if(capacity_padding[0]!=INITIAL_BYTE || capacity_progress || capacity_ready)
        return capacity_error=1;
    for(i=1;i<4600;++i) if(capacity_padding[i]) return capacity_error=2;
    capacity_padding[0]=0x5a;
    capacity_padding[4599]=0xa6;
#ifndef CAPACITY_CONSOLE
    payload(); P[1]=40; P[3]=32; P[4]=112; P[5]=72; P[6]=0x16;
    for(i=0;i<5;++i) P[7+i]="LARGE"[i];
    if(gfx_request(UDEKS_GFX_CREATE)) return capacity_error=3;
    handle=R[11];
    commands[0][1]=8; commands[0][2]=20; commands[0][3]=16; commands[0][4]=16;
    commands[1][0]=1; commands[1][1]=8; commands[1][2]=48;
    commands[1][3]=96; commands[1][4]=48;
    /* The service must reject a source reaching into the relocated stack. */
    payload(); P[2]=0xf8;
    P[3]=(*(volatile unsigned char *)3)-1; /* own cc65 SP high byte */
    P[4]=3;
    if(gfx_request(UDEKS_GFX_PRESENT)!=22) return capacity_error=4;
    payload(); P[2]=(unsigned int)commands; P[3]=(unsigned int)commands>>8; P[4]=2;
    if(gfx_request(UDEKS_GFX_PRESENT)) return capacity_error=5;
#endif
    capacity_ready=0xa5;
    for(;;) {
        if(capacity_padding[0]!=0x5a || capacity_padding[4599]!=0xa6)
            return capacity_error=6;
        ++capacity_progress;
        if(capacity_control) return 42;
#ifdef CAPACITY_CONSOLE
        /* Console cancellation/interactive stdin is not part of this test.
         * Finish a bounded computation through the ordinary EXIT trampoline. */
        if(capacity_progress==1000) return 42;
#endif
#ifndef CAPACITY_CONSOLE
        payload(); if(gfx_request(UDEKS_GFX_EVENT)) return capacity_error=7;
        if(!P[0]) return 0;
#endif
        gfx_sleep();
    }
}

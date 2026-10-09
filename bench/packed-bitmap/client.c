/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent UTRQ 0.20 boundary fixture. No resident imports or app IDs.
 * Modes: normal 128x80, wide 160x100, odd 9x7, small 32x24,
 * hold/abort/exit after one chunk. Never ships on the ordinary boot disk. */
#include <string.h>
#include "udeks/program.h"
#include "udeks/banked_graphics.h"
#define R ((volatile unsigned char *)0xf359)
#define P (R+14)
extern unsigned char __fastcall__ gfx_request(unsigned char op);
extern unsigned char gfx_sleep(void);
extern void udeks_native_console_gate(void);
unsigned char bitmap_stage,bitmap_error,bitmap_protocol,bitmap_handle;
unsigned int bitmap_uploaded;
static unsigned char width,height,stride,kind;

static void payload(void)
{
    memset((void *)P,0,24);P[1]=bitmap_handle;
}
static unsigned char version(unsigned char minor)
{
    R[5]=minor;R[6]=1;R[7]=23;R[9]=R[13]=0;R[10]=24;
    ++R[8];udeks_native_console_gate();return R[12];
}
static unsigned char begin(void)
{
    payload();P[2]=width;P[4]=height;P[5]=4;P[7]=14;
    return gfx_request(UDEKS_GFX_BITMAP_BEGIN);
}
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned int size;
    unsigned char i,n,error;
    kind=argc>1?argv[1][0]:'n';width=128;height=80;
    if(kind=='w') {width=160;height=100;}
    if(kind=='o') {width=9;height=7;}
    if(kind=='s') {width=32;height=24;}
    stride=(width+7u)/8u;size=(unsigned int)stride*height;
    payload();P[1]=20;P[3]=20;P[4]=width<40?48:width+8;
    P[5]=height<30?48:height+18;P[6]=0x16;
    memcpy((void *)(P+7),"BITMAP",6);
    bitmap_error=gfx_request(UDEKS_GFX_CREATE);
    if(bitmap_error) return bitmap_error;
    bitmap_handle=R[11];
    payload();P[0]=8;P[2]=width;P[4]=height;P[5]=4;P[7]=14;
    if(version(21)==71) bitmap_protocol|=1;
    if(version(19)==38) bitmap_protocol|=2;
    if(bitmap_protocol!=3) {bitmap_error=71;goto failed;}
    bitmap_error=begin();if(bitmap_error) goto failed;
    payload();if(gfx_request(10)!=22) {bitmap_error=22;goto failed;}
    while(bitmap_uploaded<size) {
        payload();P[2]=bitmap_uploaded;P[3]=bitmap_uploaded>>8;
        n=size-bitmap_uploaded>19?19:size-bitmap_uploaded;P[4]=n;
        for(i=0;i<n;++i) {
            P[5+i]=(unsigned char)((bitmap_uploaded+i)*37u+11u);
            if((width&7u) && (bitmap_uploaded+i+1u)%stride==0)
                P[5+i]&=(unsigned char)(255u<<(8u-(width&7u)));
        }
        bitmap_error=gfx_request(9);if(bitmap_error) goto failed;
        bitmap_uploaded+=n;
        if(kind=='h') {bitmap_stage=1;goto wait;}
        if(kind=='e') return 7;  /* EXIT with pending bytes; service must reclaim */
        if(kind=='a') {
            payload();bitmap_error=gfx_request(11);
            if(bitmap_error) goto failed;
            bitmap_stage=4;goto wait;
        }
        gfx_sleep();
    }
    do {
        payload();bitmap_error=gfx_request(10);
        if(bitmap_error==11) gfx_sleep();
    } while(bitmap_error==11);
    if(bitmap_error) goto failed;
    bitmap_stage=2;goto wait;
failed:
    bitmap_stage=255;
wait:
    for(;;) {
        payload();error=gfx_request(3);
        if(error || !P[0]) return bitmap_error;
        gfx_sleep();
    }
}

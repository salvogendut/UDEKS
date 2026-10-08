/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdio.h>
#include <string.h>
#include "udeks/window.h"
#include "udeks/window_service.h"
unsigned char udeks_graphics_record[38],input_pointer[32];
unsigned int udeks_graphics_origin_x,udeks_graphics_width;
unsigned char udeks_graphics_origin_y,udeks_graphics_height;
unsigned char focused,dragging,busy,queued,consumed;
static struct udeks_window_click click={281,45};
unsigned char udeks_graphics_event(void);
void __fastcall__ udeks_retained_read(unsigned int address);
void __fastcall__ udeks_graphics_geometry(unsigned char h);
unsigned char udeks_window_get_geometry(unsigned char h,unsigned int *x,unsigned char *y,
    unsigned int *w,unsigned char *height) {
    if(h!=2) return 1;
    *x=60;*y=50;*w=280;*height=140; return 0;
}
unsigned char udeks_window_is_focused(unsigned char h) { return focused && h==2; }
unsigned char udeks_window_is_dragging(unsigned char h) { return dragging && h==2; }
unsigned char udeks_window_update_busy(void) { return busy || dragging; }
const struct udeks_window_click * __fastcall__ udeks_window_take_click(unsigned char h) {
    if(h!=2 || !queued || dragging) return 0;
    ++consumed;return &click;
}
#define R udeks_graphics_record
#define EVENT_FUNCTION reference_event
#include "reference.h"
static unsigned char original[38], expected[38], sample[8];
int main(void) {
    unsigned int n,x;
    unsigned char expected_consumed,i;
    /* Real cc65 stack argument marshalling, including geometry and copies. */
    for(i=0;i<8;++i) sample[i]=i*31;
    udeks_retained_read((unsigned int)sample);
    if(memcmp(R+16,sample,8)) return 1;
    for(n=0;n<2048;++n) {
        memset(R,0xa5,38);
        R[5]=(n&1)?17:9; R[14]=(n&2)?7:3; R[15]=2;
        R[16]=(n&4)?24:25; R[17]=1; R[18]=140;
        focused=(n&8)!=0;dragging=(n&16)!=0;busy=(n&32)!=0;
        queued=(n&64)!=0;
        x=(n&128)?326:18;
        input_pointer[8]=x;input_pointer[9]=x>>8;
        input_pointer[10]=(n&256)?45:234;
        input_pointer[11]=(n>>9)&3;
        if(input_pointer[11]==3) input_pointer[11]=4; /* joystick fire */
        memcpy(original,R,38);consumed=0;
        if(reference_event()) return 2;
        expected_consumed=consumed;memcpy(expected,R,38);
        memcpy(R,original,38);consumed=0;
        if(udeks_graphics_event() || consumed!=expected_consumed || R[11]!=expected[11] ||
            R[14]!=expected[14]) { printf("state %u got %u/%u expected %u/%u geometry %u,%u %u,%u\n",
                n,R[14],R[11],expected[14],expected[11],udeks_graphics_origin_x,
                udeks_graphics_origin_y,udeks_graphics_width,udeks_graphics_height);return 3; }
        if(R[11]>=7 && memcmp(R+18,expected+18,3)) return 4;
        if((R[14]==3 || R[14]==4) && memcmp(R+15,expected+15,3)) return 5;
        if(R[14]==4 && R[21]!=expected[21]) return 6;
        if(memcmp(R,original,11) || memcmp(R+12,original+12,2)) return 7;
    }
    puts("PASS 2048 real-6502 input cases, geometry, copy and request guards");
    return 0;
}

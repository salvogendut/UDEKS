/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Migration candidate: ordinary relocatable task, no UAPP imports/callbacks,
 * task id, fixed app load address, or private kernel symbols. */
#include "udeks/banked_graphics.h"
#include "udeks/clock_face.h"
#include "udeks/time.h"

extern volatile unsigned char udeks_graphics_record[38];
extern volatile unsigned char udeks_time_snapshot[16];
#define R udeks_graphics_record
#define P (udeks_graphics_record+14)
#define TIME udeks_time_snapshot
extern unsigned char __fastcall__ gfx_request(unsigned char operation);
extern void gfx_sleep(void);

unsigned char udeks_native_clock_commands[UDEKS_CLOCK_FACE_COMMANDS*8u];
unsigned char udeks_native_clock_hour,udeks_native_clock_minute;
unsigned char udeks_native_clock_presents;
unsigned int udeks_native_clock_width;
unsigned char udeks_native_clock_height;
static unsigned char handle;

static void payload(void)
{
    unsigned char i;
    for(i=0;i<24;++i) P[i]=0;
    P[1]=handle;
}

static unsigned char present(void)
{
    payload();
    P[2]=(unsigned int)udeks_native_clock_commands;
    P[3]=(unsigned int)udeks_native_clock_commands>>8;
    P[4]=UDEKS_CLOCK_FACE_COMMANDS;
    if(gfx_request(UDEKS_GFX_PRESENT)) return 1;
    ++udeks_native_clock_presents;
    return 0;
}

unsigned char udeks_graphical_main(void)
{
    static unsigned char i,hour,minute;
    /* Exit status 5 means unavailable clock. Normal task retirement removes
     * our window as well, instead of leaving a stale/frozen clock face. */
    if(TIME[5]!=UDEKS_TIME_READY) return 5;
    payload(); P[1]=124; P[3]=50;
    P[4]=UDEKS_CLOCK_FACE_WIDTH; P[5]=UDEKS_CLOCK_FACE_HEIGHT; P[6]=0x0e;
    for(i=0;i<6;++i) P[7+i]="XCLOCK"[i];
    if(gfx_request(UDEKS_GFX_CREATE)) return 1;
    handle=R[11];
    /* Zeroed geometry forces the first complete presentation. */
    for(;;) {
        payload();
        P[2]=udeks_native_clock_width; P[3]=udeks_native_clock_width>>8;
        P[4]=udeks_native_clock_height;
        if(gfx_request(UDEKS_GFX_EVENT)) return 2;
        if(!P[0]) return 0;
        /* TIME is the same read-only common-RAM snapshot used by date.
         * Only root-service execution updates it; no yield between reads. */
        if(TIME[5]!=UDEKS_TIME_READY) return 5;
        {
            hour=TIME[8]; minute=TIME[9];
            if(P[0]==UDEKS_GFX_RESIZED || hour!=udeks_native_clock_hour || minute!=udeks_native_clock_minute) {
                /* Acknowledge only the geometry actually presented. */
                udeks_native_clock_width=P[4]|((unsigned int)P[5]<<8);
                udeks_native_clock_height=P[6];
                if(!udeks_clock_face(hour,minute,udeks_native_clock_width,
                    udeks_native_clock_height,udeks_native_clock_commands)) return 3;
                if(present()) return 4;
                udeks_native_clock_hour=hour; udeks_native_clock_minute=minute;
            }
        }
        gfx_sleep();
    }
}

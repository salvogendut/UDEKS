/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Migration candidate: relocatable app, no resident callback/app-id/UAPP.
 * Samples are computed once, one bounded Z80 row per cooperative iteration.
 * Resize reprojects those private samples; moves/stacking use retained data. */
#include "udeks/banked_graphics.h"
#include "udeks/wave_paths.h"
#include "worker.h"
extern volatile unsigned char udeks_graphics_record[38];
extern unsigned char __fastcall__ gfx_request(unsigned char operation);
extern void gfx_sleep(void);
extern void gfx_yield(void);
#define R udeks_graphics_record
#define P (udeks_graphics_record+14)
signed char native_wave_samples[UDEKS_WAVE_SAMPLES];
unsigned char native_wave_paths[UDEKS_WAVE_PATH_BYTES];
unsigned char native_wave_rows,native_wave_presents,native_wave_failure;
unsigned int native_wave_width;
unsigned char native_wave_height;
static unsigned char handle;
static struct udeks_wave_projection projection;

unsigned char udeks_graphical_main(void)
{
    unsigned char i,event;
    unsigned int width;
    unsigned char height;
    for(i=0;i<24;++i) P[i]=0;
    P[1]=28; P[3]=28; P[4]=176; P[5]=112; P[6]=0x0e;
    for(i=0;i<5;++i) P[7+i]="XWAVE"[i];
    if(gfx_request(UDEKS_GFX_CREATE)) return 1;
    handle=R[11];
    for(;;) {
        P[1]=handle; P[2]=native_wave_width; P[3]=native_wave_width>>8;
        P[4]=native_wave_height;
        if(gfx_request(UDEKS_GFX_EVENT)) return 2;
        event=P[0]; if(!event) return 0;
        width=P[4]|((unsigned int)P[5]<<8); height=P[6];
        if(native_wave_rows<21) {
            P[0]=5; P[1]=native_wave_rows; P[2]=1; P[3]=25;
            if(worker_request() || P[0]!=native_wave_rows+1 || P[1] || P[2]!=25) {
                native_wave_failure=3; return 3;
            }
            for(i=0;i<25;++i)
                native_wave_samples[(unsigned int)native_wave_rows*25u+i]=udeks_worker_output[i];
            ++native_wave_rows;
        } else if(event==UDEKS_GFX_RESIZED) {
            if(width!=projection.width || height!=projection.height)
                if(!udeks_wave_paths_begin(&projection,width,height)) return 4;
            /* Recheck committed geometry on every iteration, including the
             * one that publishes. A drag pauses work; a new size restarts it. */
            if(projection.done) {
                P[1]=handle;
                P[2]=(unsigned int)native_wave_paths; P[3]=(unsigned int)native_wave_paths>>8;
                P[4]=UDEKS_WAVE_PATH_BYTES&255u; P[5]=UDEKS_WAVE_PATH_BYTES>>8;
                if(gfx_request(UDEKS_GFX_PATHS)) { native_wave_failure=5; return 5; }
                native_wave_width=width; native_wave_height=height; ++native_wave_presents;
            } else {
                udeks_wave_paths_step(&projection,native_wave_samples,native_wave_paths);
                gfx_yield();
                continue;
            }
        }
        gfx_sleep();
    }
}

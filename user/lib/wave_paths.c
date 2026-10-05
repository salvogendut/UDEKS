/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/wave_paths.h"

/* One projection per process, in its relocated private BSS. Direct access
 * keeps this state machine small enough for a bounded native allocation. */
struct udeks_wave_projection udeks_wave_projection_state;
#define s (&udeks_wave_projection_state)
/* The sinc grid only has 45 horizontal and 76 vertical projected positions.
 * Build these exact integer scales once per size, instead of multiplying and
 * dividing twice for each of 548 vertices on every resize. Private app BSS;
 * neither the window manager nor the worker knows about these tables. */
static unsigned int x_scale[45];
static unsigned char y_scale[76];
unsigned char udeks_wave_paths_begin(unsigned int width, unsigned char height)
{
    unsigned char i;
    unsigned int value,remainder;
    if(width<48 || width>320 || height<48 || height>200) return 0;
    value=3; remainder=0;
    for(i=0;i<45;++i) {
        x_scale[i]=value;
        remainder+=width-6;
        while(remainder>=44) { remainder-=44; ++value; }
    }
    value=14; remainder=0;
    for(i=0;i<76;++i) {
        y_scale[i]=value;
        remainder+=height-18;
        while(remainder>=75) { remainder-=75; ++value; }
    }
    s->width=width; s->height=height; s->used=0;
    s->axis=s->strip=s->point=s->done=0;
    s->previous_x=s->previous_y=0;
    return 1;
}

unsigned char udeks_wave_paths_step(const signed char *heights, unsigned char *output)
{
    unsigned char row,col,count,budget;
    unsigned int x,y;
    if(s->done) return 1;
    budget=16;
    do {
        count=s->axis?21:25;
        row=s->axis?s->point:s->strip; col=s->axis?s->strip:s->point;
        x=x_scale[col+20u-row];
        /* Worker opcode 5's fixed sinc field gives indices 10..74. */
        y=y_scale[28+col+row-heights[(unsigned int)row*25u+col]];
        if(!s->point) {
            output[s->used++]=count|((x>>1)&128u);
            output[s->used++]=x; output[s->used++]=y;
        } else {
            output[s->used++]=x-s->previous_x;
            output[s->used++]=y-s->previous_y;
        }
        s->previous_x=x; s->previous_y=y;
        if(++s->point==count) {
            s->point=0; s->strip+=2;
            if(s->strip>=(s->axis?25:21)) {
                s->strip=0;
                if(++s->axis==2) {
                    do { output[s->used++]=0; } while(s->used&7);
                    s->done=1;
                    return 1;
                }
            }
        }
    } while(--budget);
    return 0;
}

/* Host/reference convenience; the disk client uses the bounded step API. */
#ifndef __CC65__
unsigned int udeks_wave_paths(const signed char *heights, unsigned int width,
    unsigned char height, unsigned char *output)
{
    if(!udeks_wave_paths_begin(width,height)) return 0;
    while(!udeks_wave_paths_step(heights,output)) {}
    return s->used;
}
#endif

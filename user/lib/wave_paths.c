/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/wave_paths.h"

unsigned int udeks_wave_paths(const signed char *heights, unsigned int width,
    unsigned char height, unsigned char *output)
{
    unsigned char axis,strip,row,col,point,count;
    unsigned int used,x,previous_x,y,previous_y;
    if(width<48 || width>320 || height<48 || height>200) return 0;
    used=0;
    for(axis=0;axis<2;++axis) {
        count=axis?21:25;
        for(strip=0;strip<(axis?25:21);strip+=2) {
            previous_x=previous_y=0;
            for(point=0;point<count;++point) {
                row=axis?point:strip; col=axis?strip:point;
                x=3u+((unsigned int)(col+20u-row)*4u*(width-6u))/176u;
                y=14u+((unsigned int)(28+col+row-heights[(unsigned int)row*25u+col])*(height-18u))/75u;
                if(!point) {
                    output[used++]=count|((x>>1)&128u);
                    output[used++]=x; output[used++]=y;
                } else {
                    output[used++]=x-previous_x; output[used++]=y-previous_y;
                }
                previous_x=x; previous_y=y;
            }
        }
    }
    /* One terminator followed by at most seven zero pad bytes. */
    do { output[used++]=0; } while(used&7);
    return used;
}

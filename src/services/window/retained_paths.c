/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Service-owned byte streams: no app geometry, math or foreign callbacks. */
#include "udeks/banked_graphics.h"
#include "udeks/retained_paths.h"
#include "udeks/vic_graphics.h"
#ifdef UDEKS_GRAPHICS_HOST_TEST
extern unsigned char graphics_request[38];
#define R graphics_request
#else
extern volatile unsigned char udeks_graphics_record[38];
#define R udeks_graphics_record
#endif
#define P (R+14)
#define C (R+16)
#pragma code-name("GRAPHICSPATHS")
#pragma rodata-name("GRAPHICSPATHS")
#pragma bss-name("PATHSTATE")
/* Serialized parser scratch, initialized by the lazy module installation.
 * No callbacks or yields occur during validation/copy. Paint is nonrecursive. */
static unsigned int cursor,remaining;
static unsigned char byte_index,bad,draw;
static int x,y,old_x,old_y;

#pragma code-name(push, "CODE")
unsigned int __fastcall__ udeks_retained_address(unsigned char index)
{
    return index?0xcb00u:0xc600u;
}
#pragma code-name(pop)
#pragma code-name(push, "GRAPHICSCODE")
static unsigned char next_byte(void)
{
    if(!remaining) { bad=1; return 0; }
    --remaining;
    if(byte_index==8) { udeks_banked_read(cursor);cursor+=8;byte_index=0; }
    return C[byte_index++];
}
#pragma code-name(pop)
static unsigned char paths(void)
{
    unsigned char header,points;
    bad=0; byte_index=8;
    for(;;) {
        header=next_byte();
        if(!header) {
            if(remaining>7) return 0;
            while(remaining) if(next_byte()) return 0;
            return !bad;
        }
        points=header&127u;
        if(points<2) return 0;
        x=next_byte(); if(header&128u) x+=256;
        y=next_byte();
        if((unsigned int)x>=320 || (unsigned int)y>=200) return 0;
        while(--points) {
            old_x=x; old_y=y;
            x+=(signed char)next_byte(); y+=(signed char)next_byte();
            if(bad || (unsigned int)x>=320 || (unsigned int)y>=200) return 0;
            if(draw) udeks_vic_bitmap_line(udeks_graphics_origin_x+old_x,
                udeks_graphics_origin_y+old_y,udeks_graphics_origin_x+x,
                udeks_graphics_origin_y+y,0);
        }
    }
}
void __fastcall__ udeks_retained_paths_paint(unsigned char index)
{
    cursor=udeks_retained_address(index);
    remaining=udeks_retained_lengths[index]&0x7fffu;
    draw=1; paths();
}
unsigned char __fastcall__ udeks_retained_present(unsigned char index)
{
    unsigned int source,length,limit,destination,offset;
    unsigned char format;
    source=P[2]|((unsigned int)P[3]<<8);
    format=P[0]==5;
    length=P[4];
    if(format) {
        if(R[5]<12) return 38;
        length|=(unsigned int)P[5]<<8;
        if(!length || length>UDEKS_RETAINED_CAPACITY || (length&7)) return 22;
    } else {
        if(length>48) return 22;
        length*=8;
    }
    limit=index?0x4000u:0x3500u;
    if(source<(index?0x3500u:0x2300u) || source>=limit || length>limit-source) return 22;
    if(format) {
        cursor=source;remaining=length;draw=0;
        if(!paths()) return 22;
    } else {
        for(offset=0;offset<length;offset+=8) {
            udeks_banked_read(source+offset);
            if(C[0]>2 || (C[0]<2 && C[5]!=0 && C[5]!=7)) return 22;
        }
    }
    destination=udeks_retained_address(index);
    for(offset=0;offset<length;offset+=8) {
        udeks_banked_read(source+offset);udeks_banked_write(destination+offset);
    }
    udeks_retained_lengths[index]=length|(format?0x8000u:0);
    return 0;
}

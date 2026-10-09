/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Service-owned byte streams: no app geometry, math or foreign callbacks. */
#include "udeks/banked_graphics.h"
#include "udeks/retained_paths.h"
#include "udeks/vic_graphics.h"
#include <string.h>
#ifdef UDEKS_BITMAP_REU
#include "udeks/reu_bitmap.h"
#endif
#ifdef UDEKS_GRAPHICS_HOST_TEST
extern unsigned char graphics_request[38];
#define R graphics_request
#else
extern volatile unsigned char udeks_graphics_record[38];
#define R udeks_graphics_record
#endif
#define P (R+14)
#define C (R+16)
#ifdef UDEKS_GRAPHICS_HOST_TEST
extern unsigned char graphics_pool[2304];
#define POOL(address) (graphics_pool+(address)-UDEKS_RETAINED_BASE)
#else
#define POOL(address) ((unsigned char *)(address))
#endif
#pragma code-name("GRAPHICSPATHS")
#pragma rodata-name("GRAPHICSPATHS")
#pragma bss-name("BSS")
/* Serialized parser scratch, cleared by crt0.
 * No callbacks or yields occur during validation/copy. Paint is nonrecursive. */
static unsigned int cursor,remaining;
static unsigned char byte_index,bad,draw;
static int x,y,old_x,old_y;

#pragma code-name(push, "GRAPHICSCODE")
#ifndef UDEKS_RETAINED_POOL_ASM
unsigned int __fastcall__ udeks_retained_address(unsigned char index)
{
    unsigned int address=UDEKS_RETAINED_BASE;
    while(index) address+=udeks_retained_lengths[--index]&UDEKS_RETAINED_LENGTH_MASK;
    return address;
}
#endif
/* Shared transport helper lives with the resident glue, leaving the fixed
 * lazy-install module space for the renderer. No reservation moves. */
#pragma code-name(push, "CODE")
#ifdef UDEKS_GRAPHICS_HOST_TEST
void __fastcall__ udeks_retained_read(unsigned int address)
{
    memcpy((void *)C,POOL(address),8);
}
#endif
#pragma code-name(pop)
/* All images stay packed in slot order. Admission is serialized, and only
 * validated replacements reach this compaction; no foreign pointers remain. */
#ifndef UDEKS_RETAINED_POOL_ASM
void udeks_retained_resize(unsigned char index,unsigned int length)
{
    unsigned int start,old,end;
    start=udeks_retained_address(index);
    old=udeks_retained_lengths[index]&UDEKS_RETAINED_LENGTH_MASK;
    end=udeks_retained_address(UDEKS_NATIVE_CLIENTS);
    memmove(POOL(start+length),POOL(start+old),end-start-old);
    udeks_retained_lengths[index]=length;
}
#pragma code-name(push, "GRAPHICSPATHS")
void __fastcall__ udeks_retained_discard(unsigned char index)
{
#ifdef UDEKS_BITMAP_REU
    udeks_bitmap_release(index);
#endif
    udeks_retained_resize(index,0);
}
#pragma code-name(pop)
#endif
#pragma code-name(pop)
#pragma code-name(push, "GRAPHICSCODE")
static unsigned char next_byte(void)
{
    if(!remaining) { bad=1; return 0; }
    --remaining;
    if(byte_index==8) {
        if(draw) udeks_retained_read(cursor); else udeks_banked_read(cursor);
        cursor+=8;byte_index=0;
    }
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
#pragma code-name(push, "GRAPHICSCODE")
void __fastcall__ udeks_retained_paths_paint(unsigned char index)
{
    cursor=udeks_retained_address(index);
    remaining=udeks_retained_lengths[index]&UDEKS_RETAINED_LENGTH_MASK;
    draw=1; paths();
}
#pragma code-name(pop)
unsigned char __fastcall__ udeks_retained_present_image(unsigned char index)
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
        if(length>UDEKS_RETAINED_COMMANDS) return 22;
        length*=8;
    }
    limit=(unsigned int)udeks_native_stack_pages[index]<<8;
    if(source<((unsigned int)udeks_native_base_pages[index]<<8) || source>=limit || length>limit-source) return 22;
    if(length>UDEKS_RETAINED_POOL_SIZE-(udeks_retained_address(UDEKS_NATIVE_CLIENTS)-
        UDEKS_RETAINED_BASE-(udeks_retained_lengths[index]&UDEKS_RETAINED_LENGTH_MASK))) return 12;
    if(format) {
        cursor=source;remaining=length;draw=0;
        if(!paths()) return 22;
    } else {
        for(offset=0;offset<length;offset+=8) {
            udeks_banked_read(source+offset);
            if(C[0]>10 || (C[0]>2 && R[5]<13) || (C[0]<2 && C[5]!=0 && C[5]!=7)) return 22;
        }
    }
    destination=udeks_retained_address(index);
    udeks_retained_resize(index,length);
    for(offset=0;offset<length;offset+=8) {
        udeks_banked_read(source+offset);memcpy(POOL(destination+offset),(const void *)C,8);
    }
    udeks_retained_lengths[index]=length|(format?0x8000u:0);
    return 0;
}
#pragma code-name(push, "CODE")
unsigned char __fastcall__ udeks_retained_present(unsigned char index)
{
#ifdef UDEKS_BITMAP_REU
    unsigned char error;
#endif
    /* Pending upload bytes are never a legacy image replacement. Keep this
     * guard in resident service glue, outside the fixed path-code overlay. */
    if(udeks_retained_lengths[index]&0x2000u) return 16;
#ifdef UDEKS_BITMAP_REU
    error=udeks_retained_present_image(index);
    /* Release only after a successful, fully validated legacy replacement.
     * Rejections must retain the old bitmap, including its REU ownership. */
    if(!error) udeks_bitmap_release(index);
    return error;
#else
    return udeks_retained_present_image(index);
#endif
}
#pragma code-name(pop)

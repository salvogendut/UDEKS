/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Fixed service binding of bitmap_store.c's independently tested contract.
 * Uses the existing retained pool allocator, not a second pool or heap.
 * No callbacks/yields: the common request stays stable for this call. */
#include <string.h>
#include "udeks/retained_bitmap.h"
#include "udeks/retained_paths.h"
#include "udeks/task_request.h"
#include "udeks/vic_graphics.h"

#if UDEKS_BITMAP_LENGTH != UDEKS_RETAINED_LENGTH_MASK || \
    UDEKS_BITMAP_POOL_BYTES != UDEKS_RETAINED_POOL_SIZE || \
    UDEKS_BITMAP_PATHS != UDEKS_RETAINED_PATH_FLAG
#error Bitmap and legacy retained-store layout disagree
#endif

#ifdef UDEKS_GRAPHICS_HOST_TEST
extern unsigned char graphics_request[38],graphics_pool[2304];
#define P (graphics_request+14)
#define POOL(address) (graphics_pool+(address)-UDEKS_RETAINED_BASE)
#else
extern volatile unsigned char udeks_graphics_record[38];
#define P (udeks_graphics_record+14)
#define POOL(address) ((unsigned char *)(address))
#endif

static unsigned char zeroes(unsigned char first)
{
    while(first<24) if(P[first++]) return 0;
    return 1;
}

unsigned char __fastcall__ udeks_retained_bitmap_request(unsigned char index)
{
    unsigned int size,received,at,x;
    unsigned int *record;
    unsigned char *header;
    unsigned char i,count,stride,padding;
    if(index>=UDEKS_BITMAP_CLIENTS) return UDEKS_TREQ_EINVAL;
    record=udeks_retained_lengths+index;
    if(P[0]==UDEKS_BITMAP_BEGIN) {
        x=P[5]|((unsigned int)P[6]<<8);
        if(P[3] || !P[2] || P[2]>240 || !P[4] || P[4]>175 ||
           x>320u-P[2] || P[7]>(unsigned char)(200u-P[4]) || !zeroes(8))
            return UDEKS_TREQ_EINVAL;
        if(*record) return UDEKS_TREQ_EBUSY;
        stride=(unsigned char)(P[2]+7u)>>3;
        size=UDEKS_BITMAP_HEADER+(unsigned int)stride*P[4];
        if(size>UDEKS_RETAINED_BASE+UDEKS_RETAINED_POOL_SIZE-
                udeks_retained_address(UDEKS_BITMAP_CLIENTS)) return UDEKS_TREQ_ENOMEM;
        udeks_retained_resize(index,size);
        header=POOL(udeks_retained_address(index));
        memcpy(header,(const void *)(P+5),3);
        header[3]=P[2];header[4]=P[4];header[5]=stride;
        header[6]=header[7]=0;
        *record|=UDEKS_BITMAP_FORMAT|UDEKS_BITMAP_PENDING;
        return 0;
    }
    size=*record;
    if((size&~UDEKS_BITMAP_LENGTH)!=(UDEKS_BITMAP_FORMAT|UDEKS_BITMAP_PENDING))
        return UDEKS_TREQ_EINVAL;
    size=(size&UDEKS_BITMAP_LENGTH)-UDEKS_BITMAP_HEADER;
    header=POOL(udeks_retained_address(index));
    received=header[6]|((unsigned int)header[7]<<8);
    if(P[0]==UDEKS_BITMAP_WRITE) {
        at=P[2]|((unsigned int)P[3]<<8);count=P[4];
        if(!count || count>UDEKS_BITMAP_CHUNK || at!=received || at>size ||
           count>size-at || !zeroes(5u+count)) return UDEKS_TREQ_EINVAL;
        stride=header[5];padding=header[3]&7u;
        if(padding) padding=(1u<<(8u-padding))-1u;
        for(i=0;i<count;++i)
            if((at+i+1u)%stride==0 && (P[5+i]&padding)) return UDEKS_TREQ_EINVAL;
        memcpy(header+UDEKS_BITMAP_HEADER+at,(const void *)(P+5),count);
        received+=count;header[6]=received;header[7]=received>>8;
        return 0;
    }
    if(!zeroes(2)) return UDEKS_TREQ_EINVAL;
    if(P[0]==UDEKS_BITMAP_COMMIT) {
        if(received!=size) return UDEKS_TREQ_EINVAL;
        *record&=~UDEKS_BITMAP_PENDING;
        return 0;
    }
    if(P[0]==UDEKS_BITMAP_ABORT) {
        udeks_retained_discard(index);
        return 0;
    }
    return UDEKS_TREQ_EINVAL;
}

#ifndef UDEKS_BITMAP_RENDER_ASM
/* C pixel oracle; the production renderer is the equivalent service helper. */
void __fastcall__ udeks_retained_bitmap_paint(unsigned char index)
{
    const unsigned char *header,*pixels;
    unsigned int left,x,y;
    unsigned char row,col,byte,stride,height;
    if(index>=UDEKS_BITMAP_CLIENTS ||
       (udeks_retained_lengths[index]&~UDEKS_BITMAP_LENGTH)!=UDEKS_BITMAP_FORMAT)
        return;
    header=POOL(udeks_retained_address(index));
    left=udeks_graphics_origin_x+header[0]+((unsigned int)header[1]<<8);
    y=udeks_graphics_origin_y+header[2];stride=header[5];height=header[4];
    pixels=header+UDEKS_BITMAP_HEADER;
    for(row=0;row<height;++row,++y) {
        for(col=0;col<stride;++col) {
            byte=*pixels++;x=left+(unsigned int)col*8;
            while(byte) {
                if(byte&128u) udeks_vic_bitmap_pixel(x,y,0);
                byte<<=1;++x;
            }
        }
    }
}
#endif

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* 16-bit target proof: actual fixed-pool C + ASM allocator vs portable oracle. */
#include <stdio.h>
#include <string.h>
#include "udeks/bitmap_store.h"
#include "udeks/retained_bitmap.h"
#include "udeks/retained_paths.h"

#pragma bss-name(push,"POOL")
unsigned char graphics_pool[2304];
#pragma bss-name(pop)
volatile unsigned char udeks_graphics_record[38];
unsigned int udeks_retained_lengths[4],udeks_graphics_origin_x;
unsigned char udeks_graphics_origin_y;
static unsigned char reference_pool[2304],payload[24],canvas[8000],expected[8000];
static unsigned int reference_lengths[4],checks;
static unsigned char failed;
static struct udeks_bitmap_store reference={reference_pool,reference_lengths};
#define CHECK(x) do {++checks;if(!(x)){failed=1;printf("FAIL retained bitmap line %u\n",(unsigned)__LINE__);}} while(0)

void udeks_vic_bitmap_pixel(int x,int y,unsigned char color)
{
    unsigned int bit;
    CHECK(color==0);
    if(x<0 || x>=320 || y<0 || y>=200) return;
    bit=(unsigned)y*320+(unsigned)x;
    canvas[bit>>3]|=128u>>(bit&7u);
}
static void compare(void)
{
    CHECK(!memcmp(graphics_pool,reference_pool,sizeof(graphics_pool)));
    CHECK(!memcmp(udeks_retained_lengths,reference_lengths,sizeof(reference_lengths)));
    CHECK(*(unsigned char *)0x12ff==0x5a && *(unsigned char *)0x1c00==0xa5);
}
static void request(unsigned char index,unsigned char error)
{
    unsigned char result;
    memcpy((void *)(udeks_graphics_record+14),payload,24);
    result=udeks_bitmap_request(&reference,index,payload);
    CHECK(result==error);
    CHECK(udeks_retained_bitmap_request(index)==result);
    CHECK(!memcmp((const void *)(udeks_graphics_record+14),payload,24));
    compare();
}
static void begin(unsigned char index,unsigned char width,unsigned char height,unsigned char error)
{
    memset(payload,0,24);payload[0]=8;payload[1]=1;
    payload[2]=width;payload[4]=height;payload[5]=4;payload[7]=14;
    request(index,error);
}
static void discard(unsigned char index)
{
    udeks_bitmap_discard(&reference,index);udeks_retained_discard(index);compare();
}
static void upload(unsigned char index,unsigned int size)
{
    unsigned int at=0;
    unsigned char count,n;
    while(at<size) {
        memset(payload,0,24);payload[0]=9;payload[1]=1;payload[2]=at;payload[3]=at>>8;
        count=size-at>19?19:size-at;payload[4]=count;
        for(n=0;n<count;++n) payload[5+n]=(unsigned char)((at+n)*37u);
        request(index,0);at+=count;
    }
}
static void paint(unsigned char index,unsigned char width,unsigned char height)
{
    unsigned int x,y,bit,at;
    unsigned char stride=width/8;
    memset(canvas,0,8000);memset(expected,0,8000);
    udeks_retained_bitmap_paint(index);
    for(y=0;y<height;++y) for(x=0;x<width;++x) {
        at=y*stride+x/8;
        if(((unsigned char)(at*37u)&(128u>>(x&7))) &&
            udeks_graphics_origin_x+4+x<320 && udeks_graphics_origin_y+14+y<200) {
            bit=((unsigned int)udeks_graphics_origin_y+14+y)*320+udeks_graphics_origin_x+4+x;
            expected[bit>>3]|=128u>>(bit&7);
        }
    }
    CHECK(!memcmp(canvas,expected,8000));compare();
}
/* Exercise replacement as well as begin/discard: legacy PRESENT can grow or
 * shrink an existing nonempty stream with peers on either side. The oracle
 * uses ordinary C offsets, independently of the production ASM addresses. */
static void resize_replacements(void)
{
    static const unsigned int flags[4]={0,UDEKS_BITMAP_PATHS,UDEKS_BITMAP_FORMAT,
        UDEKS_BITMAP_FORMAT|UDEKS_BITMAP_PENDING};
    unsigned int iteration,start,old,end,size,address;
    unsigned char index,i,seed=73;
    for(iteration=0;iteration<512;++iteration) {
        seed=(unsigned char)(seed*33u+17u);index=seed&3u;
        size=(unsigned int)seed+(iteration&255u);
        start=end=0;
        for(i=0;i<4;++i) {
            if(i<index) start+=reference_lengths[i]&UDEKS_BITMAP_LENGTH;
            end+=reference_lengths[i]&UDEKS_BITMAP_LENGTH;
        }
        old=reference_lengths[index]&UDEKS_BITMAP_LENGTH;
        /* Four <=510-byte images always fit; caller admission is mandatory. */
        memmove(reference_pool+start+size,reference_pool+start+old,end-start-old);
        reference_lengths[index]=size;
        udeks_retained_resize(index,size);compare();
        memset(reference_pool+start,seed,size);memset(graphics_pool+start,seed,size);
        /* All live formats must contribute only their physical byte length. */
        reference_lengths[index]|=flags[iteration&3u];
        udeks_retained_lengths[index]=reference_lengths[index];
        address=0x1300;
        for(i=0;i<=4;++i) {
            CHECK(udeks_retained_address(i)==address);
            if(i<4) address+=reference_lengths[i]&UDEKS_BITMAP_LENGTH;
        }
        compare();
    }
    for(index=0;index<4;++index) discard(index);
}
int main(void)
{
    unsigned char i;
    memset(graphics_pool,0xa5,2304);memset(reference_pool,0xa5,2304);
    *(unsigned char *)0x12ff=0x5a;*(unsigned char *)0x1c00=0xa5;
    CHECK((unsigned)graphics_pool==0x1300);
    reference_lengths[3]=udeks_retained_lengths[3]=297;
    begin(0,160,100,12);reference_lengths[3]=udeks_retained_lengths[3]=296;
    begin(0,160,100,0);begin(1,8,1,12);upload(0,2000);
    udeks_retained_bitmap_paint(0);CHECK(!memcmp(canvas,expected,8000));
    memset(payload,0,24);payload[0]=10;payload[1]=1;request(0,0);
    paint(0,160,100);udeks_graphics_origin_x=260;udeks_graphics_origin_y=160;paint(0,160,100);
    discard(0);discard(3);
    udeks_graphics_origin_x=udeks_graphics_origin_y=0;
    for(i=0;i<4;++i) {
        begin(i,8,1,0);upload(i,1);
        memset(payload,0,24);payload[0]=10;payload[1]=1;request(i,0);
    }
    discard(1);discard(0);discard(3);discard(2);
    reference_lengths[0]=udeks_retained_lengths[0]=344;
    reference_lengths[1]=udeks_retained_lengths[1]=0x8468;
    begin(3,88,63,0);discard(0);discard(1);begin(0,8,1,0);
    memset(payload,0,24);payload[0]=11;payload[1]=1;request(3,0);discard(0);
    begin(2,9,1,0);
    memset(payload,0,24);payload[0]=9;payload[1]=1;payload[4]=2;
    payload[5]=255;payload[6]=1;request(2,22);payload[6]=128;request(2,0);
    memset(payload,0,24);payload[0]=10;payload[1]=1;payload[2]=1;request(2,22);
    payload[2]=0;request(2,0);discard(2);
    begin(255,8,1,22);
    resize_replacements();
    if(failed) return 1;
    printf("PASS %u retained bitmap checks: shared allocator, request parity and pixels\n",checks);
    return 0;
}

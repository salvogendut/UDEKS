/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Execute the actual core on sim6502: 16-bit unsigned arithmetic, masks,
 * packed pool compaction and a guard after the last byte all matter here. */
#include <stdio.h>
#include <string.h>
#include "udeks/bitmap_store.h"

static unsigned char guarded[2306],snapshot[2306],p[24];
static unsigned int lengths[4],saved_lengths[4],checks;
static struct udeks_bitmap_store store={guarded+1,lengths};
static unsigned char failed;
#define CHECK(value) do { ++checks; if(!(value)) { \
    printf("FAIL packed bitmap at line %u\n",(unsigned int)__LINE__); failed=1; } } while(0)
static void request(unsigned char i,unsigned char error)
{
    memcpy(snapshot,guarded,sizeof(guarded));
    memcpy(saved_lengths,lengths,sizeof(lengths));
    CHECK(udeks_bitmap_request(&store,i,p)==error);
    if(error) {
        CHECK(!memcmp(snapshot,guarded,sizeof(guarded)));
        CHECK(!memcmp(saved_lengths,lengths,sizeof(lengths)));
    }
    CHECK(guarded[0]==0xa5 && guarded[2305]==0xa5);
}
static void begin(unsigned char i,unsigned char width,unsigned char height,unsigned char error)
{
    memset(p,0,sizeof(p));p[0]=8;p[1]=1;p[2]=width;p[4]=height;p[5]=4;p[7]=14;
    request(i,error);
}
static void upload(unsigned char i,unsigned int size)
{
    unsigned int at=0;
    unsigned char n,count;
    while(at<size) {
        memset(p,0,sizeof(p));p[0]=9;p[1]=1;p[2]=at;p[3]=at>>8;
        count=size-at>19?19:size-at;p[4]=count;
        for(n=0;n<count;++n) p[5+n]=(unsigned char)((at+n)*37u);
        request(i,0);at+=count;
        CHECK(!udeks_bitmap_view(&store,i));
    }
}
int main(void)
{
    const unsigned char *image;
    unsigned int n;
    memset(guarded,0xa5,sizeof(guarded));
    lengths[3]=297;begin(0,160,100,12);
    lengths[3]=296;begin(0,160,100,0);
    CHECK(lengths[0]==0x67d8u);
    begin(0,8,1,16);
    memset(p,0,sizeof(p));p[0]=10;p[1]=1;request(0,22);
    upload(0,2000);
    memset(p,0,sizeof(p));p[0]=10;p[1]=1;request(0,0);
    CHECK(lengths[0]==0x47d8u);
    image=udeks_bitmap_view(&store,0);CHECK(image!=0);
    if(image) {
        CHECK(image[3]==160 && image[4]==100 && image[5]==20);
        for(n=0;n<2000;++n) CHECK(image[8+n]==(unsigned char)(n*37u));
    }
    begin(1,8,1,12);
    udeks_bitmap_discard(&store,0);
    for(n=0;n<296;++n) CHECK(guarded[n+1]==0xa5);
    CHECK(lengths[0]==0 && lengths[3]==296);
    udeks_bitmap_discard(&store,3);
    begin(3,128,80,0);upload(3,1280);
    begin(0,8,1,0);
    /* Inserting another owner moved the still-pending image. */
    memset(p,0,sizeof(p));p[0]=10;p[1]=1;request(3,0);
    image=udeks_bitmap_view(&store,3);CHECK(image!=0);
    if(image) for(n=0;n<1280;++n) CHECK(image[8+n]==(unsigned char)(n*37u));
    memset(p,0,sizeof(p));p[0]=11;p[1]=1;request(0,0);
    image=udeks_bitmap_view(&store,3);CHECK(image!=0);
    if(image) CHECK(image[6]==0 && image[7]==5);
    udeks_bitmap_discard(&store,3);
    begin(0,9,1,0);
    memset(p,0,sizeof(p));p[0]=9;p[1]=1;p[4]=2;p[5]=255;p[6]=1;request(0,22);
    p[6]=128;request(0,0);
    memset(p,0,sizeof(p));p[0]=10;p[1]=1;request(0,0);
    CHECK(udeks_bitmap_view(&store,0)[9]==128);
    udeks_bitmap_discard(&store,0);
    begin(255,8,1,22);
    if(failed) return 1;
    printf("PASS %u packed bitmap checks on 6502; production integration pending\n",checks);
    return 0;
}

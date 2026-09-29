/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Linked with the REAL C fill/clip and service ASM pixel/span primitives.
 * CLIENT is a mock bounded row painter. COMMIT is a memory-model copy, not the
 * VIC common-RAM copier. No apps, NMI, boot disk or visible graphics instance.
 */
#include <string.h>
#include "expected.h"

#define V(a) (*(volatile unsigned char *)(a))
#define RECORD 0x7FC0u
extern unsigned char udeks_vic_bitmap_shadow[8000];
extern void runtime_install(void), runtime_irq_start(void), runtime_irq_stop(void), runtime_check_memory(void);
extern unsigned char runtime_call(void);
extern unsigned long runtime_irq_count;
extern unsigned char runtime_irq_bad, runtime_zp_bad, runtime_hw_bad, runtime_flags_bad;
extern unsigned char runtime_sw_bad, runtime_guard_bad, runtime_ush_bad, runtime_low_water, runtime_seen_flags;
static unsigned char failure, current_case, low, high, title[96];
static unsigned int pages;
static void check(unsigned char ok, unsigned char code) { if (!ok && !failure) failure=code; }
static unsigned char request(unsigned char op) { packet.op=op; return runtime_call(); }
static unsigned int checksum(void)
{
    unsigned int i;
    low=0x57;high=0x13;
    for(i=0;i<8000u;++i) {low+=udeks_vic_bitmap_shadow[i];high+=low;}
    return low | ((unsigned int)high << 8);
}
void udeks_vic_bitmap_commit_page(unsigned char page)
{
    unsigned int at, end;
    check(page<32,1);++pages;
    at=(unsigned int)page*256u;end=at+256u;if(end>8000u)end=8000u;
    while(at<end){V(0x6000u+at)=udeks_vic_bitmap_shadow[at];++at;}
}
static void drive(void)
{
    struct udeks_repaint_lane_work work;
    unsigned int limit, x;
    unsigned char result, y;
    pages=0;
    for(limit=0;limit<1000u;++limit){
        result=repaint_frontend_poll(1,&work);
        if(result==UDEKS_REPAINT_IDLE)break;
        if(result==UDEKS_REPAINT_YIELD)continue;
        if(result!=UDEKS_REPAINT_OK && result!=UDEKS_LANE_BACKEND_REQUIRED){check(0,2);break;}
        if(work.ticket.phase==UDEKS_REPAINT_CLIENT){
            check(result==UDEKS_LANE_BACKEND_REQUIRED,3);
            check(repaint_receipt_validate(&work.ticket)==0,4);
            udeks_vic_bitmap_set_clip(work.clip.left,work.clip.top,
                work.clip.right-work.clip.left,work.clip.bottom-work.clip.top);
            y=work.clip.top+work.ticket.cursor;
            check(y<work.clip.bottom,5);
            for(x=work.clip.left;x<work.clip.right;++x)
                udeks_vic_bitmap_pixel(x,y,(x*3u+y*5u)%7u<3u?0:7);
            udeks_vic_bitmap_reset_clip();
            check(repaint_receipt_ack(&work.ticket,y+1u<work.clip.bottom)==0,6);
        }else check(result==0,7);
        check(*(unsigned int *)0xE1B0u==0 && *(unsigned int *)0xE1B2u==0 &&
              *(unsigned int *)0xE1B4u==320 && *(unsigned int *)0xE1B6u==200,8);
    }
    check(limit<1000u && pages==32,9);
}
static void cancel_on_glyph(void)
{
    struct udeks_repaint_lane_work old;
    unsigned int before, limit;
    unsigned char dirty[32];
    check(request(REPAINT_REQUEST)==0,10);
    for(limit=0;limit<100u;++limit){
        check(repaint_frontend_poll(1,&old)==0,11);check(request(REPAINT_PEEK)==0,11);old=packet.work;
        if(old.ticket.phase==UDEKS_REPAINT_CHROME && old.ticket.cursor==4)break;
        /* frontend already executed exactly one step; next PEEK is unacknowledged. */
    }
    check(limit<100u,13);before=checksum();
    memcpy(dirty,(const void *)0xE190u,32);
    check(request(REPAINT_CHANGED)==0,14);
    windows[0].title=(const unsigned char *)1;
    udeks_vic_bitmap_set_clip(111,77,2,3);
    check(lane_raster_step(&old)==UDEKS_REPAINT_STALE,15);
    check(checksum()==before && memcmp(dirty,(const void *)0xE190u,32)==0,16);
    check(*(unsigned int *)0xE1B0u==111 && *(unsigned int *)0xE1B2u==77 &&
          *(unsigned int *)0xE1B4u==113 && *(unsigned int *)0xE1B6u==80,17);
    check(request(REPAINT_ABORT)==0,18);
}

static void protocol_probe(void)
{
    struct udeks_repaint_lane before;
    unsigned int pixels;
    unsigned char n;
    check(request(REPAINT_INIT)==0,24);
    packet.damage.left=0;packet.damage.right=320;packet.damage.top=0;packet.damage.bottom=200;
    check(request(REPAINT_REQUEST)==0,24);before=packet.snapshot;
    memset(udeks_vic_bitmap_shadow,0x69,8000);memset((void *)0xE190u,0,32);
    udeks_vic_bitmap_set_clip(111,77,2,3);pixels=checksum();
    for(n=0;n<4u;++n) {
        memset(packet.scenes,0,sizeof(packet.scenes));memset(packet.reserved,0,4);
        packet.count=REPAINT_SCENE_FORMAT;
        packet.scenes[0].rank=1;packet.scenes[0].flags=UDEKS_WINDOW_FLAG_VISIBLE;
        packet.scenes[0].width=48;packet.scenes[0].height=48;
        if(n==0)packet.count=4;
        else if(n==1)packet.reserved[3]=1;
        else if(n==2)packet.scenes[0].x=65535u;
        else packet.scenes[0].rank=5;
        check(request(REPAINT_PEEK)==UDEKS_REPAINT_INVALID,25);
        check(memcmp(&before,&packet.snapshot,sizeof(before))==0 && checksum()==pixels,26);
        check(*(unsigned int *)0xE1B0u==111 && *(unsigned int *)0xE1B2u==77 &&
            *(unsigned int *)0xE1B4u==113 && *(unsigned int *)0xE1B6u==80,26);
    }
    V(RECORD+9)=n;
}

int main(void)
{
    unsigned int i, value;
    struct udeks_window *w=&windows[0];
    for(i=0;i<8096u;++i)V(RECORD+i)=0;
    V(RECORD)='R';V(RECORD+1)='A';V(RECORD+2)='S';V(RECORD+3)='T';
    V(RECORD+4)=2;V(RECORD+5)=1;
    memset(windows,0,sizeof(windows));
    runtime_install();
    for(i=0;i<200u;++i)((unsigned int *)0xE000u)[i]=(i&248u)*40u+(i&7u);
    memset(title,'M',sizeof(title));
    runtime_irq_start();protocol_probe();
    for(current_case=0;current_case<8u;++current_case){
        check(request(REPAINT_INIT)==0,19);
        w->x=cases[current_case].x;w->y=cases[current_case].y;
        w->width=cases[current_case].width;w->height=cases[current_case].height;
        w->flags=cases[current_case].flags|UDEKS_WINDOW_FLAG_VISIBLE;w->z=1;
        if(current_case==0)w->title=0;
        else if(current_case==5)w->title=title;
        else w->title=(const unsigned char *)"aZ ? Xclock";
        packet.damage.left=0;packet.damage.right=320;packet.damage.top=0;packet.damage.bottom=200;
        memset(udeks_vic_bitmap_shadow,0x69,8000);
        memset((void *)0xE190u,0,32);udeks_vic_bitmap_reset_clip();
        check(request(REPAINT_REQUEST)==0,20);drive();
        value=checksum();check(value==expected[current_case],21);
        V(RECORD+32u+current_case*2u)=value;V(RECORD+33u+current_case*2u)=value>>8;
        for(i=0;i<8000u;++i)check(V(0x6000u+i)==udeks_vic_bitmap_shadow[i],22);
        for(i=0;i<32u;++i)check(V(0xE190u+i)==0,23);
    }
    for(i=0;i<8000u;++i)V(RECORD+64u+i)=V(0x6000u+i);
    cancel_on_glyph();
    runtime_irq_stop();runtime_check_memory();
    V(RECORD+7)=failure;
    for(i=0;i<4u;++i)V(RECORD+12u+i)=runtime_irq_count>>(i*8u);
    V(RECORD+16)=runtime_irq_bad;V(RECORD+17)=runtime_zp_bad;
    V(RECORD+18)=runtime_hw_bad;V(RECORD+19)=runtime_flags_bad;
    V(RECORD+20)=runtime_sw_bad;V(RECORD+21)=runtime_guard_bad;
    V(RECORD+22)=runtime_ush_bad;V(RECORD+23)=runtime_low_water;V(RECORD+24)=runtime_seen_flags;
    V(RECORD+8)=current_case;V(RECORD+5)=2;return 0;
}

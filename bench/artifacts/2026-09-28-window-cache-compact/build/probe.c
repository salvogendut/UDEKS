extern unsigned char runtime_accept(void), runtime_step(void);
extern unsigned int runtime_accept_count;
extern volatile unsigned char cache_accept_state,cache_owner,cache_phase;
extern volatile unsigned int cache_ticket;
/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Real compiled caller: continuation tickets, pixel/dirty oracle on host. */
#include <stdint.h>
#define V(a) (*(volatile uint8_t *)(a))
#define W(a) (*(volatile uint16_t *)(a))
#define RECORD 0x7FC0u
#define SHADOW 0xA1E0u
#define DIRTY 0xE190u
#define GEO 0xF7A1u
extern void runtime_install(void), runtime_irq_start(void), runtime_irq_stop(void);
extern void nmi_probe_start(void), nmi_probe_stop(void), nmi_probe_publish(void);
extern uint8_t runtime_call(void);
extern void runtime_check_memory(void);
extern uint32_t runtime_irq_count;
extern uint16_t runtime_call_count;
extern uint8_t runtime_irq_bad, runtime_zp_bad, runtime_hw_bad, runtime_flags_bad;
extern uint8_t runtime_sw_bad, runtime_guard_bad, runtime_ush_bad, runtime_low_water;
extern uint8_t runtime_seen_flags;
static uint8_t failure, images;
static uint16_t rows, ticket;
static void check(uint8_t ok, uint8_t code) {if (!ok && !failure) failure=code;}
static void geometry(uint16_t x,uint8_t y,uint16_t w,uint8_t h) {
    W(GEO)=x;W(GEO+2)=w;V(GEO+4)=y;V(GEO+5)=h;
}
static uint8_t call(uint8_t op,uint8_t owner,uint16_t generation) {
    V(0xF790)=op;V(0xF792)=owner;W(0xF793)=generation;
    return runtime_call();
}
static void reject_step(uint8_t owner,uint16_t gen,uint8_t code) {
    check(call(4,owner,gen)==1,code);
    check(V(0xF792)==owner && W(0xF793)==gen,code);
}
static void preflight(void) {
    check(call(0,0,0)==0 && W(0xF793)==1 && V(0xF791)==0,1);
    ticket=1;
    geometry(7,17,168,104);V(0xF795)=0;
    check(call(2,1,0)==1,2);
    V(0xF795)=1;
    check(call(2,1,0)==0 && V(0xF791)==1,2);
    check(call(3,1,ticket)==1,3);
    reject_step(1,2,4);reject_step(2,1,4);
    check(call(2,2,0)==2,5);
    check(call(1,0,0)==0 && W(0xF793)==2 && V(0xF791)==0,6);
    reject_step(1,1,7);
    ticket=2;
    check(call(255,1,1)==1,8);
    geometry(0,0,220,160);check(call(2,1,0)==1,9);
    geometry(319,0,17,1);check(call(2,1,0)==1,9);
    geometry(7,17,168,104);check(call(2,1,0)==0,10);
    check(call(1,0,0)==0 && W(0xF793)==3,10);ticket=3;
    runtime_check_memory();
}
static void background(uint8_t other) {
    uint16_t i;for(i=0;i<8000u;++i)V(SHADOW+i)=(uint8_t)(i*(other?31u:13u)+(other?19u:7u));
}
static void drive(uint8_t mode,uint8_t h) {
    uint8_t i;
    for(i=0;i<h;++i) {
        V(0xF792)=4;W(0xF793)=0xbeef;V(0xF791)=0xff;
        check(runtime_step()==0 && W(0xF793)==ticket &&
            V(0xF791)==(i+1==h?2u:(mode?3u:1u)),11);
        ++rows;
        if((i&7u)==0)runtime_check_memory();
    }
    reject_step(1,ticket,12);
}
static void image(uint16_t x,uint8_t y,uint16_t xx,uint8_t yy,uint16_t w,uint8_t h) {
    geometry(x,y,w,h);check(call(2,1,0)==0 && W(0xF793)==ticket,13);drive(0,h);
#if CASE == 1
    background(1);
#endif
    geometry(xx,yy,w,h);check(call(3,1,0)==0,15);drive(1,h);++images;
#if CASE == 1
    geometry(151,83,w,h);check(call(3,1,0)==0,17);drive(1,h);++images;
#endif
    check(call(1,0,0)==0 && W(0xF793)==ticket+1,18);++ticket;
}
int main(void) {
    uint8_t i;uint16_t j;
#if CASE == 0
    uint8_t a,b;
#endif
    for(j=0;j<8096u;++j)V(RECORD+j)=0;
    V(RECORD)='A';V(RECORD+1)='V';V(RECORD+2)='L';V(RECORD+3)='D';
    V(RECORD+4)=1;V(RECORD+5)=1;V(RECORD+6)=CASE;
    for(j=0;j<736u;++j)V(0xF3A0u+j)=(uint8_t)(j*11u+0x37u);
    V(0xF3ED)=0;V(0xF7A0)=0x5a;V(0xF7D8)=0xa5;
    runtime_install();runtime_irq_start();nmi_probe_start();
    /* No C call before acceptance, across all four caller I/D modes. */
    for(i=0;i<4;++i)check(call(0,0,0)==0xff,21);
    for(i=0;i<17;++i) {
        unsigned char result=runtime_accept();
        if(result)break;
        /* Simulate an intervening VIC workspace user between pages. */
        runtime_check_memory();
        V(0xF780)=0xa5;V(0xF781)=0x5a;V(0xF782)=0xa5;
    }
#if BADCASE
    check(cache_accept_state==0xff,22);
    check(runtime_accept_count==(BADCASE==2?1u:17u),22);
    check(call(0,0,0)==0xff && call(4,1,1)==0xff,23);
    for(j=0;j<8000;++j)V(SHADOW+j)=0;
    for(i=0;i<32;++i)V(DIRTY+i)=0;
    goto finish;
#else
    check(cache_accept_state==0x80 && runtime_accept_count==17,22);
    check(cache_ticket==1 && cache_owner==0 && cache_phase==0,22);
    preflight();
#endif
    background(0);for(i=0;i<32;++i)V(DIRTY+i)=0;
#if CASE == 0
    for(a=0;a<8;++a)for(b=0;b<8;++b)image(a,128,b,a*8+b,17,1);
    image(0,129,0,64,320,1);image(319,199,319,199,1,1);
#else
    image(7,7,100,40,168,104);
#endif
finish:
    runtime_check_memory();
    for(j=0;j<26;++j)V(RECORD+38+j)=V(0xF7B0+j);
    for(j=0;j<736u;++j)if(0xF3A0u+j!=0xF3EDu)
        check(V(0xF3A0u+j)==(uint8_t)(j*11u+0x37u),19);
    check(V(0xF7A0)==0x5a && V(0xF7D8)==0xa5,20);
    runtime_irq_stop();nmi_probe_stop();
    V(RECORD+7)=failure;W(RECORD+8)=rows;W(RECORD+10)=runtime_call_count;
    W(RECORD+12)=(uint16_t)runtime_irq_count;V(RECORD+14)=images;
    V(RECORD+15)=runtime_irq_bad;V(RECORD+16)=runtime_zp_bad;
    V(RECORD+17)=runtime_hw_bad;V(RECORD+18)=runtime_flags_bad;
    V(RECORD+19)=runtime_sw_bad;V(RECORD+20)=runtime_guard_bad;
    V(RECORD+21)=runtime_ush_bad;V(RECORD+22)=runtime_low_water;
    V(RECORD+23)=runtime_seen_flags;W(RECORD+24)=(uint16_t)(runtime_irq_count>>16);
    for(j=0;j<8000u;++j)V(RECORD+64u+j)=V(SHADOW+j);
    for(i=0;i<32;++i)V(RECORD+8064u+i)=V(DIRTY+i);
    nmi_probe_publish();V(RECORD+5)=2;return 0;
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Actual cc65 policy/blitter integration on a private bank-1 stack.
 * Diagnostic caller only. Production cache continuations remain uninstalled. */
#include <stdint.h>
#define V(address) (*(volatile uint8_t *)(address))
#define LEASE 0x4CD0u
#define GEOMETRY 0x4CDDu
#define ROW 0x4CE3u
#define IMAGE 0x4E00u
#define CAPACITY 3584u
#define OP 0xF790u
#define ARGS 0xF793u
#define LAST_A 0xF79Au
#define LAST_X 0xF79Bu
#define IN_GEOMETRY 0xF7A1u
#define OUT_ROW 0xF7A7u
#define OUT_LEASE 0xF7B0u
#define ROW_PARAMS 0xF780u
#define SHADOW 0xA1E0u
#define DIRTY 0xE190u
#define RECORD 0x7FC0u
extern void runtime_install(void), runtime_irq_start(void), runtime_irq_stop(void);
extern uint8_t runtime_call(void);
extern void runtime_row(void), runtime_check_memory(void);
extern uint32_t runtime_irq_count;
extern uint16_t runtime_call_count;
extern uint8_t runtime_irq_bad, runtime_zp_bad, runtime_hw_bad, runtime_flags_bad;
extern uint8_t runtime_sw_bad, runtime_guard_bad, runtime_ush_bad, runtime_low_water;
extern uint8_t runtime_seen_flags;
static uint8_t failure, before[13];
static uint16_t rows;
static uint8_t images;

static void check(uint8_t ok, uint8_t code) {if (!ok && !failure) failure=code;}
static void word(uint16_t address,uint16_t value) {
    V(address)=(uint8_t)value;V(address+1)=(uint8_t)(value>>8);
}
static uint16_t read_word(uint16_t address) {
    return (uint16_t)V(address)|((uint16_t)V(address+1)<<8);
}
static void geometry(uint16_t x,uint8_t y,uint16_t w,uint8_t h) {
    word(IN_GEOMETRY,x);word(IN_GEOMETRY+2,w);
    V(IN_GEOMETRY+4)=y;V(IN_GEOMETRY+5)=h;
}
static uint8_t call(uint8_t op,uint8_t owner,uint16_t gen,uint16_t last) {
    V(OP)=op;
    if(op<=1)word(ARGS,LEASE);
    else if(op==2) {
        word(ARGS,GEOMETRY);word(ARGS+2,gen);V(ARGS+4)=owner;word(ARGS+5,LEASE);
    } else {
        word(ARGS,gen);V(ARGS+2)=owner;word(ARGS+3,LEASE);
    }
    word(LAST_A,last);
    return runtime_call();
}
static void save(void) {
    uint8_t i;for(i=0;i<13;++i)before[i]=V(OUT_LEASE+i);
}
static void unchanged(void) {
    uint8_t i;for(i=0;i<13;++i)check(V(OUT_LEASE+i)==before[i],2);
}
static void rejection(uint8_t op,uint8_t owner,uint16_t gen,uint16_t last,uint8_t status) {
    save();check(call(op,owner,gen,last)==status,1);unchanged();
}
static void preflight(void) {
    call(0,0,0,CAPACITY);
    check(read_word(OUT_LEASE+8)==CAPACITY && V(OUT_LEASE+11)==0,3);
    geometry(7,17,168,104);
    rejection(2,1,1,0,1);                /* no explicit complete eligibility */
    rejection(2,1,0,1,1);                /* zero generation */
    rejection(2,0,1,1,1);                /* invalid owner */
    check(call(2,1,65535u,1)==0,4);
    rejection(3,1,65535u,GEOMETRY,1);     /* cannot paste partial capture */
    rejection(2,2,1,1,2);                /* capture busy, no takeover */
    rejection(4,1,1,ROW,1);              /* stale prepare */
    rejection(5,1,65535u,1,1);           /* wrong row */
    save();call(1,0,0,2);unchanged();      /* different owner cannot invalidate */
    call(1,0,0,1);
    rejection(5,1,65535u,0,1);           /* cancelled continuation */
    check(call(2,1,1,1)==0,4);            /* generation wrap/new generation */
    rejection(5,1,65535u,0,1);
    call(1,0,0,0);
    rejection(255,1,1,0,1);             /* bounded function selection */
    geometry(0,0,220,160);
    rejection(2,1,2,1,1);                /* oversized for private-stack layout */
    geometry(319,0,17,1);
    rejection(2,1,2,1,1);
    geometry(0,199,17,2);
    rejection(2,1,2,1,1);
    runtime_check_memory();
}
static void drive(uint8_t mode,uint16_t gen,uint16_t x,uint8_t y,
                  uint16_t w,uint8_t h) {
    uint8_t i,j,tail,mask,stride,raw;
    uint16_t offset,expected,address;
    stride=(w+7u)>>3;raw=(w+(x&7u)+7u)>>3;
    mask=(w&7u)?(uint8_t)(255u<<(8u-(w&7u))):255u;
    for(i=0;i<h;++i) {
        check(call(4,1,gen,ROW)==0,5);
        expected=(uint16_t)((y+i)&248u)*40u+((y+i)&7u)+(x&0xFFF8u);
        offset=read_word(OUT_ROW);address=IMAGE+read_word(OUT_ROW+2);
        check(offset==expected && address==IMAGE+(uint16_t)i*stride,6);
        check(V(OUT_ROW+4)==stride && V(OUT_ROW+5)==raw &&
            V(OUT_ROW+6)==(x&7u) && V(OUT_ROW+7)==mask && V(OUT_ROW+8)==mode,7);
        word(ROW_PARAMS,offset);word(ROW_PARAMS+2,address);
        for(j=4;j<9;++j)V(ROW_PARAMS+j)=V(OUT_ROW+j);
        runtime_row();++rows;
        if(!mode) {
            tail=V(ROW_PARAMS+9);
            check((tail & (uint8_t)~mask)==0,8);
        }
        check(call(5,1,gen,i)==0,9);
        check(V(OUT_LEASE+12)==i+1 && V(OUT_LEASE+11)==
            (i+1==h?2:(mode?3:1)),10);
        if((i&7u)==0)runtime_check_memory();
    }
    rejection(5,1,gen,h-1,1);             /* duplicate acknowledgement */
}
static void background(uint8_t other) {
    uint16_t i;for(i=0;i<8000u;++i)V(SHADOW+i)=(uint8_t)(i*(other?31u:13u)+(other?19u:7u));
}
static void image(uint16_t x,uint8_t y,uint16_t xx,uint8_t yy,
                  uint16_t w,uint8_t h,uint16_t gen) {
    geometry(x,y,w,h);check(call(2,1,gen,1)==0,11);
    drive(0,gen,x,y,w,h);
#if CASE == 1
    background(1);                       /* prove reuse after source changed */
#endif
    geometry(xx,yy,w,h);
    check(call(3,1,gen,GEOMETRY)==0,12);
    drive(1,gen,xx,yy,w,h);
    ++images;
}
int main(void) {
    uint8_t i;uint16_t j,gen=1;
#if CASE == 0
    uint8_t a,b;
#endif
    for(j=0;j<8096u;++j)V(RECORD+j)=0;
    V(RECORD)='C';V(RECORD+1)='R';V(RECORD+2)='U';V(RECORD+3)='N';
    V(RECORD+4)=1;V(RECORD+5)=1;V(RECORD+6)=CASE;
    for(j=0;j<736u;++j)V(0xF3A0u+j)=(uint8_t)(j*11u+0x37u);
    V(0xF3ED)=0;
    V(0xF7A0)=0x5a;V(0xF7D8)=0xa5;
    runtime_install();runtime_irq_start();preflight();
    background(0);for(i=0;i<32;++i)V(DIRTY+i)=0;
#if CASE == 0
    for(a=0;a<8;++a)for(b=0;b<8;++b)image(a,128,b,a*8+b,17,1,gen++);
    image(0,129,0,64,320,1,gen++);image(319,199,319,199,1,1,gen++);
#else
    image(7,7,100,40,168,104,gen);
#endif
    runtime_check_memory();
    for(j=0;j<736u;++j)if(0xF3A0u+j!=0xF3EDu)
        check(V(0xF3A0u+j)==(uint8_t)(j*11u+0x37u),13);
    check(V(0xF7A0)==0x5a && V(0xF7D8)==0xa5,14);
    runtime_irq_stop();
    V(RECORD+7)=failure;word(RECORD+8,rows);word(RECORD+10,runtime_call_count);
    word(RECORD+12,runtime_irq_count);V(RECORD+14)=images;
    V(RECORD+15)=runtime_irq_bad;V(RECORD+16)=runtime_zp_bad;
    V(RECORD+17)=runtime_hw_bad;V(RECORD+18)=runtime_flags_bad;
    V(RECORD+19)=runtime_sw_bad;V(RECORD+20)=runtime_guard_bad;
    V(RECORD+21)=runtime_ush_bad;V(RECORD+22)=runtime_low_water;
    V(RECORD+23)=runtime_seen_flags;
    word(RECORD+24,(uint16_t)(runtime_irq_count>>16));
    for(j=0;j<8000u;++j)V(RECORD+64u+j)=V(SHADOW+j);
    for(i=0;i<32;++i)V(RECORD+8064u+i)=V(DIRTY+i);
    V(RECORD+5)=2;
    return 0;
}

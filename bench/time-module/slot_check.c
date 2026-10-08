/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Real 6502 candidate/veneer, isolated from simulator ZP by call.s. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern const unsigned char module_image[], slot_image[], validation_cases[];
extern const unsigned int slot_size, validation_count;
extern unsigned int module_entry;
extern unsigned char module_hour, module_minute, module_second, module_stack_error;
unsigned char module_call(void);

#define MEM(a) (*(volatile unsigned char *)(a))
#define SLOT 0x9300u
#define LIMIT 0x96a8u
#define TIME_STATE MEM(0xf205)
#define CHECK(c) check((c), __LINE__)
enum { STARTUP, PHASE, RESULT, CALLS, DESIRED, SEEN_PHASE, RECURSIVE, BEGIN_EARLY,
       CONTROL, POLL, SET, STATE, VALIDATE, POISON_STACK };
static unsigned int image_size, i, k, word, sum;
static unsigned char rc, expected, width;
static unsigned char slot_before[LIMIT-SLOT];
static unsigned char time_before[24], cia_before[8];
static const unsigned char *record;
static unsigned long calls;

static void check(unsigned char ok, unsigned int line)
{
    if(!ok) {
        printf("FAIL slot lifecycle line %u case %u: rc=%u state=%u\n",
               line,i,rc,MEM((unsigned int)slot_image[22]|((unsigned int)slot_image[23]<<8)));
        exit(1);
    }
}
static unsigned int read_word(const unsigned char *p)
{ return p[0]|((unsigned int)p[1]<<8); }
static unsigned int address(unsigned char index)
{ return read_word(slot_image+2*index); }
static void write_word(unsigned int where,unsigned int value)
{ MEM(where)=value; MEM(where+1)=value>>8; }
static unsigned char invoke(unsigned char index,unsigned char a,unsigned char x,unsigned char y)
{
    module_entry=address(index);
    module_hour=a; module_minute=x; module_second=y;
    rc=module_call(); ++calls;
    CHECK(!module_stack_error);
    CHECK(MEM(0xee00)==0x5a && MEM(0xef00)==0xa5);
    CHECK(MEM(SLOT-1)==0x37 && MEM(LIMIT)==0x73);
    return rc;
}
static unsigned char control(unsigned char action,unsigned int count)
{ return invoke(CONTROL,action,count,count>>8); }
static void reset(void)
{
    memcpy((void *)0x8000,slot_image,slot_size);
    MEM(address(STATE))=0;
    MEM(0xee00)=0x5a; MEM(0xef00)=0xa5;
    MEM(SLOT-1)=0x37; MEM(LIMIT)=0x73;
    memset((void *)0xf110,0,16);
}
static void real_image(void)
{
    memset((void *)SLOT,0xa5,LIMIT-SLOT);
    memcpy((void *)SLOT,module_image,image_size);
}
static void reseal(unsigned int size)
{
    sum=0;
    for(k=0;k<size;++k) if(k!=16 && k!=17) sum+=MEM(SLOT+k);
    write_word(SLOT+16,sum);
}
static void stub(unsigned int offset,unsigned char counter,unsigned char result)
{
    unsigned int p=SLOT+offset;
    MEM(p)=0xee; write_word(p+1,0xf110+counter); /* INC counter */
    MEM(p+3)=0xa9; MEM(p+4)=result; MEM(p+5)=0x60;
}
static void synthetic(unsigned char start_error,unsigned char poll_error,unsigned char stop_error)
{
    real_image();
    memset((void *)(SLOT+48),0xea,128);
    write_word(SLOT+10,176); write_word(SLOT+12,3);
    write_word(SLOT+20,SLOT+64); write_word(SLOT+42,SLOT+96);
    write_word(SLOT+44,SLOT+128); write_word(SLOT+46,SLOT+160);
    stub(64,0,0); stub(96,1,start_error); stub(128,2,poll_error); stub(160,3,stop_error);
    /* Request records its original A/X/Y before returning. */
    MEM(SLOT+67)=0x8d; write_word(SLOT+68,0xf118);
    MEM(SLOT+70)=0x8e; write_word(SLOT+71,0xf119);
    MEM(SLOT+73)=0x8c; write_word(SLOT+74,0xf11a);
    MEM(SLOT+76)=0xa9; MEM(SLOT+77)=0; MEM(SLOT+78)=0x60;
    /* Start observes unpublished state and cleared BSS. */
    MEM(SLOT+99)=0xad; write_word(SLOT+100,address(STATE));
    MEM(SLOT+102)=0x8d; write_word(SLOT+103,0xf114);
    MEM(SLOT+105)=0xad; write_word(SLOT+106,SLOT+176);
    MEM(SLOT+108)=0x8d; write_word(SLOT+109,0xf115);
    MEM(SLOT+111)=0xa9; MEM(SLOT+112)=start_error; MEM(SLOT+113)=0x60;
    memset((void *)(SLOT+176),0xa5,3);
    reseal(176);
}

int main(void)
{
    image_size=read_word(module_image+10);
    /* Every startup result (including failure) is permanently cached. */
    for(i=0;i<256;++i) {
        reset(); MEM(address(DESIRED))=i;
        CHECK(control(1,0)==11); CHECK(MEM(address(STATE))==0);
        CHECK(invoke(STARTUP,0,0,0)==i);
        CHECK(MEM(address(CALLS))==1 && MEM(address(PHASE))==2);
        CHECK(MEM(address(SEEN_PHASE))==1 && MEM(address(RECURSIVE))==1);
        CHECK(MEM(address(BEGIN_EARLY))==11 && MEM(address(RESULT))==i);
        memset((void *)0xf090,0,24); /* damaged public SREG is not authority */
        MEM(address(DESIRED))=i^255;
        CHECK(invoke(POISON_STACK,0,0,0)==i);
        CHECK(invoke(STARTUP,0,0,0)==i);
        CHECK(MEM(address(CALLS))==1 && MEM(address(PHASE))==2);
        if(i) { CHECK(control(1,0)==11); CHECK(MEM(address(STATE))==0); }
    }
    puts("PASS startup: all 256 results, recursive entry, damaged SREG, unusable C stack");
    reset(); CHECK(invoke(STARTUP,0,0,0)==0);
    CHECK(control(4,0)==22); CHECK(control(255,0)==22);
    CHECK(control(2,image_size)==22); CHECK(control(0,0)==0);

    /* Independent Python oracle, with checksum resealed around metadata
       mutations; validate-only must not write any payload/snapshot/state. */
    for(i=0;i<validation_count;++i) {
        real_image(); record=validation_cases+7*i;
        width=record[1]; word=read_word(record+2);
        if(width) MEM(SLOT+record[0])=word;
        if(width==2) MEM(SLOT+record[0]+1)=word>>8;
        if(width!=3) reseal(image_size);
        memcpy(slot_before,(const void *)SLOT,LIMIT-SLOT);
        MEM(address(STATE))=i%3;
        memset((void *)0xf200,0x5a,24); memset((void *)0xdc08,0xa5,8);
        memcpy(time_before,(const void *)0xf200,24);
        memcpy(cia_before,(const void *)0xdc08,8);
        word=read_word(record+4); expected=record[6];
        CHECK(invoke(VALIDATE,0,word,word>>8)==expected);
        CHECK(MEM(address(STATE))==i%3 && TIME_STATE==0x5a);
        CHECK(!memcmp(slot_before,(const void *)SLOT,LIMIT-SLOT));
        CHECK(!memcmp(time_before,(const void *)0xf200,24));
        CHECK(!memcmp(cia_before,(const void *)0xdc08,8));
        if(expected) {
            /* Also exercise the public commit path, which retires a rejected
               load to offline without executing any payload entry. */
            MEM(address(STATE))=1;
            CHECK(control(2,word)==8);
            CHECK(!MEM(address(STATE)) && !TIME_STATE);
            CHECK(!memcmp(slot_before,(const void *)SLOT,LIMIT-SLOT));
            time_before[5]=0;
            CHECK(!memcmp(time_before,(const void *)0xf200,24));
            CHECK(!memcmp(cia_before,(const void *)0xdc08,8));
        }
    }
    printf("PASS %u independent validator cases; rejection executes no code\n",validation_count);

    reset(); CHECK(invoke(STARTUP,0,0,0)==0);
    CHECK(invoke(SET,23,59,58)==1); CHECK(invoke(POLL,0,0,0)==0);
    CHECK(control(3,0)==0); /* idempotent stop while absent */
    CHECK(control(1,0)==0); CHECK(control(1,0)==16);
    CHECK(MEM(address(STATE))==1 && !TIME_STATE);
    CHECK(invoke(SET,1,2,3)==1); CHECK(invoke(POLL,0,0,0)==0);
    synthetic(0,0,0);
    CHECK(control(2,176)==0); CHECK(MEM(address(STATE))==2);
    CHECK(MEM(0xf111)==1 && MEM(0xf114)==1 && MEM(0xf115)==0);
    CHECK(!MEM(SLOT+176) && !MEM(SLOT+177) && !MEM(SLOT+178));
    CHECK(MEM(SLOT+179)==module_image[179]); /* clear did not overrun */
    CHECK(control(1,0)==16); CHECK(control(2,176)==16);
    /* Cache, not header, controls all post-registration dispatch. */
    memset((void *)SLOT,0,48);
    CHECK(invoke(SET,23,59,58)==0);
    CHECK(MEM(0xf118)==23 && MEM(0xf119)==59 && MEM(0xf11a)==58);
    CHECK(invoke(POLL,0,0,0)==0); CHECK(MEM(0xf112)==1);
    CHECK(control(3,0)==0); CHECK(MEM(0xf113)==1);
    CHECK(control(3,0)==0); CHECK(MEM(0xf113)==1);
    CHECK(invoke(SET,0,0,0)==1);

    CHECK(control(1,0)==0); synthetic(9,0,0);
    CHECK(control(2,176)==5); CHECK(!MEM(address(STATE)) && !TIME_STATE);
    CHECK(invoke(POLL,0,0,0)==0); CHECK(invoke(SET,0,0,0)==1);
    CHECK(control(1,0)==0); synthetic(0,9,0);
    CHECK(control(2,176)==0); CHECK(invoke(POLL,0,0,0)==0);
    CHECK(!MEM(address(STATE)) && TIME_STATE==0x80);
    CHECK(invoke(SET,0,0,0)==1);
    CHECK(control(1,0)==0); synthetic(0,0,9);
    CHECK(control(2,176)==0); CHECK(control(3,0)==5);
    CHECK(!MEM(address(STATE)) && !TIME_STATE);
    CHECK(control(1,0)==0); CHECK(control(3,0)==0); /* abort partial load */
    CHECK(!MEM(address(STATE)) && !TIME_STATE);
    puts("PASS lifecycle: publication, abort, duplicate load, cached vectors, start/poll/stop errors");

    /* Actual sealed time implementation through registered dispatch only. */
    for(i=0;i<3;++i) {
        CHECK(control(1,0)==0); real_image();
        MEM(0xf0c7)=1;
        MEM(0xdc08)=0; MEM(0xdc09)=0x45; MEM(0xdc0a)=0x23; MEM(0xdc0b)=0x81;
        CHECK(control(2,image_size)==0); CHECK(TIME_STATE==2);
        CHECK(invoke(SET,23,59,58)==0); CHECK(invoke(POLL,0,0,0)==0);
        CHECK(MEM(0xf208)==23 && MEM(0xf209)==59 && MEM(0xf20a)==58);
        CHECK(control(3,0)==0); CHECK(!TIME_STATE);
        CHECK(invoke(SET,0,0,0)==1); CHECK(invoke(POLL,0,0,0)==0);
        CHECK(!memcmp((const void *)SLOT,module_image,image_size));
    }
    printf("PASS sealed TIME.SVC load/set/poll/stop/reload; %lu protected calls\n",calls);
    return 0;
}

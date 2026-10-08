/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern const unsigned char module_image[],request_image[],sdk_image[],gate_image[],router_image[],common_image[],bootfs_image[];
extern const unsigned int request_size,sdk_size,gate_size,router_size,common_size,bootfs_size,sdk_errno;
extern unsigned int module_entry;
extern unsigned char module_hour,module_minute,module_second,module_stack_error;
unsigned char module_call(void);
#define MEM(a) (*(volatile unsigned char *)(a))
#define REC ((unsigned char *)0xf359)
#define SLOT ((unsigned char *)0x93d0)
#define CHECK(c) check((c),__LINE__)
enum { START,PHASE,RESULT,STATE,POLL,SET,SDK,SDK_BAD,TRANSPORT,RETIRED,RETIRE_COUNT,STORAGE_COUNT };
static unsigned int i,j,n,calls;
static unsigned char rc,seq=0,slot_copy[728],time_copy[24],cia_copy[8];
static void check(unsigned char c,unsigned int line)
{ if(!c) { printf("FAIL request line %u case %u: rc=%u errno=%u state=%u\n",line,i,rc,REC[12],REC[6]);exit(1); } }
static unsigned int word(const unsigned char *p) { return p[0]|((unsigned int)p[1]<<8); }
static unsigned int address(unsigned char index) { return word(request_image+2*index); }
static unsigned char call(unsigned int entry,unsigned char a,unsigned char x,unsigned char y)
{
    module_entry=entry;module_hour=a;module_minute=x;module_second=y;
    rc=module_call();++calls;
    CHECK(!module_stack_error);
    CHECK(MEM(0xee00)==0x5a && MEM(0xef00)==0xa5);
    CHECK(MEM(0xe700)==0x5a && MEM(0xe800)==0xa5);
    CHECK(MEM(0x93cf)==0x37 && MEM(0x96a8)==0x73);
    return rc;
}
static unsigned char sdk(unsigned char action,unsigned int received)
{
    unsigned char r=call(address(SDK),action,received,received>>8);
    CHECK(!MEM(address(SDK_BAD)));return r;
}
static void request(unsigned char action,unsigned int received)
{
    memset(REC,0,38);memcpy(REC,"UTRQ",4);REC[5]=19;REC[6]=1;REC[7]=28;
    REC[8]=++seq;REC[10]=3;REC[14]=action;REC[15]=received;REC[16]=received>>8;
}
static void snapshot(void)
{ memcpy(slot_copy,SLOT,728);memcpy(time_copy,(void *)0xf200,24);memcpy(cia_copy,(void *)0xdc08,8); }
static void rejected(unsigned char error)
{
    snapshot();call(0xcf30,0,0,0);
    CHECK(REC[6]==128 && REC[11]==0 && REC[12]==error && REC[8]==seq);
    CHECK(!memcmp(slot_copy,SLOT,728) && !memcmp(time_copy,(void *)0xf200,24) && !memcmp(cia_copy,(void *)0xdc08,8));
    CHECK(!MEM(address(STATE)));
}
static void retire(unsigned char tag)
{
    unsigned char before=MEM(address(RETIRE_COUNT));
    CHECK(call(0xc883,tag,0x5a,0xa5)==tag);
    CHECK(MEM(address(RETIRED))==tag && MEM(address(RETIRE_COUNT))==(unsigned char)(before+1));
}
int main(void)
{
    memcpy((void *)0x8000,request_image,request_size);
    memcpy((void *)0xa000,sdk_image,sdk_size);
    memcpy((void *)0xcf00,gate_image,gate_size);
    memcpy((void *)0xc880,router_image,router_size);
    memcpy((void *)0xf800,common_image,common_size);
    memcpy((void *)0xf3ef,bootfs_image,bootfs_size);
    MEM(0xfe20)=0x4c;MEM(0xfe21)=address(TRANSPORT);MEM(0xfe22)=address(TRANSPORT)>>8;
    MEM(0xee00)=0x5a;MEM(0xef00)=0xa5;MEM(0xe700)=0x5a;MEM(0xe800)=0xa5;
    MEM(0x93cf)=0x37;MEM(0x96a8)=0x73;
    MEM(0xf110)=0;MEM(0xf285)=2; /* trusted root + active foreground */
    MEM(address(RETIRE_COUNT))=0;MEM(address(STORAGE_COUNT))=0;
    memset(SLOT,0xa5,728);MEM(address(STATE))=0;
    request(1,0);rejected(11); /* startup still active/unattempted */
    CHECK(call(address(START),0,0,0)==0);
    /* Exercise the REAL CF30 signature/state/version decoder, not a fake. */
    for(i=0;i<5;++i) { request(1,0);REC[i]^=1;rejected(71); }
    for(i=20;i<256;++i) { request(1,0);REC[5]=i;rejected(71); }
    for(i=0;i<19;++i) { request(1,0);REC[5]=i;rejected(22); }
    request(1,0);REC[6]=2;rejected(71);
    for(i=1;i<256;++i) {
        request(1,0);REC[9]=i;rejected(22);
        request(1,0);REC[13]=i;rejected(22);
        request(1,0);MEM(0xf110)=i;rejected(22);MEM(0xf110)=0;
    }
    for(i=0;i<256;++i) {
        if(i!=3) { request(1,0);REC[10]=i;rejected(22); }
        if(i!=2) { request(1,0);MEM(0xf285)=i;rejected(22);MEM(0xf285)=2; }
        if(i>=4) { request(i,0);rejected(22); }
    }
    puts("PASS real request envelope, reserved fields, startup and trusted caller rejection (no module/snapshot/CIA mutation)");
    request(0,0);REC[7]=29;call(0xcf30,0,0,0);CHECK(REC[12]==38);
    CHECK(MEM(address(STORAGE_COUNT))==1); /* unknown operations keep fallback */
    /* STOP is valid while absent; the ABI ignores count-word for non-COMMIT. */
    request(3,65535u);call(0xcf30,0,0,0);CHECK(REC[6]==2 && REC[11]==1 && REC[14]==0);
    CHECK(sdk(0,0)==0);CHECK(sdk(1,0)==1);
    CHECK(sdk(1,0)==255 && MEM(sdk_errno)==16);
    for(i=0;i<11;++i) if(i!=9) { retire(i);CHECK(MEM(address(STATE))==1); }
    retire(9);CHECK(!MEM(address(STATE)) && !MEM(0xf205));
    CHECK(sdk(1,0)==1);memcpy(SLOT,module_image,word(module_image+10));SLOT[0]^=1;
    CHECK(sdk(2,word(module_image+10))==255 && MEM(sdk_errno)==8 && !MEM(address(STATE)));
    puts("PASS abandoned foreground lease cleanup; other retirements leave it alone; bad COMMIT goes offline");
    for(j=0;j<3;++j) {
        CHECK(sdk(1,0)==1);n=word(module_image+10);memcpy(SLOT,module_image,n);
        MEM(0xf0c7)=1;MEM(0xdc08)=0;MEM(0xdc09)=0x45;MEM(0xdc0a)=0x23;MEM(0xdc0b)=0x81;
        CHECK(sdk(2,n)==2 && MEM(0xf205)==2);
        retire(9);CHECK(MEM(address(STATE))==2); /* loader exit keeps service */
        CHECK(call(address(SET),23,59,58)==0);CHECK(call(address(POLL),0,0,0)==0);
        CHECK(MEM(0xf208)==23 && MEM(0xf209)==59 && MEM(0xf20a)==58);
        CHECK(sdk(0,0)==2);CHECK(sdk(1,0)==255 && MEM(sdk_errno)==16);
        CHECK(sdk(3,0)==0 && !MEM(0xf205));
    }
    printf("PASS private console ZP, live software stack and decimal flag restored; real TIME.SVC start/poll/stop/reload; %u calls\n",calls);
    return 0;
}

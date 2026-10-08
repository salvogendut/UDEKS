/* SPDX-License-Identifier: GPL-3.0-or-later */
/* CPU/RAM qualification, not an emulation of CIA latching or mains timing. */
#include <stdio.h>
#include <string.h>

extern const unsigned char module_image[];
extern unsigned int module_entry;
extern unsigned char module_hour, module_minute, module_second;
extern unsigned char module_stack_error;
unsigned char module_call(void);
#define MEM(a) (*(volatile unsigned char *)(a))
#define TIME ((volatile unsigned char *)0xf200)
#define TOD ((volatile unsigned char *)0xdc08)
static unsigned int base, size, bss, i;
static unsigned char hh, mm, ss, result;
static unsigned char expected_hour, expected_minute, expected_second;
static unsigned long expected, actual, cases;
static unsigned char saved_time[24], saved_cia[8];
static unsigned char field, decoded, valid;

static unsigned int word(unsigned char n)
{
    return module_image[n] | ((unsigned int)module_image[n+1] << 8);
}
static unsigned char invoke(unsigned char offset)
{
    module_entry=word(offset);
    result=module_call();
    if(module_stack_error || MEM(0xee00)!=0x5a || MEM(0xef00)!=0xa5) {
        puts("FAIL module stack/guard"); return 255;
    }
    ++cases;
    return result;
}
static unsigned char bcd(unsigned char n) { return ((n/10)<<4)|(n%10); }
static unsigned char check_time(void)
{
    if(TIME[8]!=hh || TIME[9]!=mm || TIME[10]!=ss || TIME[11]) return 0;
    expected=((unsigned long)hh*3600UL+(unsigned long)mm*60UL+ss)*60UL;
    actual=((unsigned long)MEM(0xa0)<<16)|((unsigned int)MEM(0xa1)<<8)|MEM(0xa2);
    if(actual!=expected) return 0;
    expected_hour=hh<12?bcd(hh):(bcd(hh-12)|0x80);
    expected_minute=bcd(mm); expected_second=bcd(ss);
    if(TOD[0] || TOD[1]!=expected_second || TOD[2]!=expected_minute) return 0;
    /* Existing setter uses $00/$80 for midnight/noon, not $12/$92. */
    return TOD[3]==expected_hour;
}

int main(void)
{
    base=word(8); size=word(10); bss=word(12);
    memcpy((void *)base,module_image,size);
    memset((void *)(base+size),0,bss);
    MEM(base-1)=0x37; MEM(base+size+bss)=0x73;
    MEM(0xee00)=0x5a; MEM(0xef00)=0xa5;
    /* PAL/NTSC control selection, start/stop/restart, and stopped polling. */
    for(i=1;i<=2;++i) {
        MEM(0xf0c7)=i;
        TOD[0]=0; TOD[1]=0x45; TOD[2]=0x23; TOD[3]=0x81;
        MEM(0xdc0e)=0x15; MEM(0xdc0f)=0x91;
        if(invoke(42) || TIME[5]!=2 || TIME[8]!=13 || TIME[9]!=23 || TIME[10]!=45 ||
           MEM(0xdc0e)!=(i==1?0x95:0x15) || MEM(0xdc0f)!=0x91) {
            puts("FAIL start/timing control"); return 1;
        }
        if(invoke(46) || TIME[5] || invoke(44)!=1) { puts("FAIL stop/poll"); return 1; }
        if(invoke(42) || TIME[5]!=2) { puts("FAIL restart"); return 1; }
    }
    module_hour=24; module_minute=0; module_second=0;
    if(invoke(20)!=1) { puts("FAIL invalid-hour rejection (negative control)"); return 1; }
    for(hh=0;hh<24;++hh) for(mm=0;mm<60;++mm) for(ss=0;ss<60;++ss) {
        module_hour=hh; module_minute=mm; module_second=ss;
        if(invoke(20) || !check_time()) {
            printf("FAIL set/TI mirror at %u:%u:%u result=%u TI=%lu expected=%lu TOD=%02x/%02x/%02x/%02x snapshot=%u:%u:%u.%u\n",
                hh,mm,ss,result,actual,expected,TOD[3],TOD[2],TOD[1],TOD[0],TIME[8],TIME[9],TIME[10],TIME[11]);
            printf("expected BCD %02x/%02x/%02x\n",bcd(hh),bcd(mm),bcd(ss));
            return 1;
        }
        if(invoke(44) || !check_time()) { puts("FAIL poll/BCD conversion"); return 1; }
    }
    memcpy(saved_time,(const void *)0xf200,24); memcpy(saved_cia,(const void *)0xdc08,8);
    for(i=0;i<256;++i) {
        module_hour=0; module_minute=0; module_second=0;
        if(i>=24) { module_hour=i; if(invoke(20)!=1) return 2; module_hour=0; }
        if(i>=60) {
            module_minute=i; if(invoke(20)!=1) return 3; module_minute=0;
            module_second=i; if(invoke(20)!=1) return 4;
        }
        if(memcmp(saved_time,(const void *)0xf200,24) || memcmp(saved_cia,(const void *)0xdc08,8)) {
            puts("FAIL invalid setter mutated state"); return 1;
        }
    }
    /* All raw encodings of each TOD register, including ignored flag bits
       and invalid values. Match the pre-extraction conversion/range rules,
       not a new stricter BCD policy. Tenths is still sampled last. */
    for(field=0;field<4;++field) for(i=0;i<256;++i) {
        hh=1; mm=2; ss=3;
        TOD[3]=1; TOD[2]=2; TOD[1]=3; TOD[0]=0;
        TOD[field]=i;
        if(field==0) { decoded=i; valid=i<10; }
        else {
            decoded=i & (field==3 ? 0x1f : 0x7f);
            decoded=((decoded>>4)*10)+(decoded&15);
            valid=decoded <= (field==3 ? 12 : 59);
            if(field==3 && valid) {
                if(i & 0x80) { decoded+=12; if(decoded==24) decoded=12; }
                else if(decoded==12) decoded=0;
            }
        }
        result=invoke(44);
        if(result!=(valid ? 0 : 1)) { puts("FAIL raw TOD range"); return 1; }
        if(valid && TIME[11-field]!=decoded) { puts("FAIL raw TOD conversion"); return 1; }
    }
    /* Both fixed diagnostic counters retain their 16-bit carry semantics. */
    module_hour=1; module_minute=2; module_second=3;
    if(invoke(20)) return 1;
    TIME[16]=255; TIME[17]=255; TIME[18]=255; TIME[19]=255;
    TOD[1]=4;
    if(invoke(44) || TIME[16] || TIME[17] || TIME[18] || TIME[19]) {
        puts("FAIL diagnostic counter rollover"); return 1;
    }
    if(MEM(base-1)!=0x37 || MEM(base+size+bss)!=0x73 ||
       memcmp((const void *)base,module_image,size)) {
        puts("FAIL module code/bounds"); return 1;
    }
    printf("PASS %lu module calls: all 86400 times, 1024 raw TOD cases, counter rollover, TI/BCD, lifecycle, guards, atomic invalid-set rejection\n",cases);
    return 0;
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "udeks/cbm_mutate.h"
#include "udeks/iec_slow.h"
uint8_t reference_mutate(uint8_t, uint8_t, const uint8_t *, const uint8_t *);
extern uint8_t test_begin_error, test_command_error, test_status_error, test_untalk_error;
extern uint8_t test_device;
extern uint16_t test_calls[7], test_status[80], test_size, test_pos;
void test_reset(void);
static uint8_t src[16], dst[16], saved[38], errors[4], unit, op;
static uint16_t calls[7], input[80], size, cases;
static void reset(void)
{
    test_reset(); memcpy(test_status,input,sizeof(input)); test_size=size;
    test_begin_error=errors[0]; test_command_error=errors[1];
    test_status_error=errors[2]; test_untalk_error=errors[3];
}
static void check(const uint8_t *s, const uint8_t *d)
{
    uint8_t result, actual, length, device;
    uint16_t pos;
    reset(); result=reference_mutate(unit,op,s,d);
    memcpy(saved,udeks_iec_filename,38); memcpy(calls,test_calls,sizeof(calls));
    length=udeks_iec_filename_length; device=test_device; pos=test_pos;
    reset();
    actual=udeks_cbm_mutate(unit,op,s,d);
    if (result!=actual ||
        memcmp(saved,udeks_iec_filename,38) || memcmp(calls,test_calls,sizeof(calls)) ||
        length!=udeks_iec_filename_length || device!=test_device || pos!=test_pos) {
        printf("FAIL mutation case %u op %u result %u/%u length %u/%u pos %u/%u\n",cases,op,result,actual,length,udeks_iec_filename_length,pos,test_pos);
        printf("names %.*s / %.*s\n",length,saved,udeks_iec_filename_length,udeks_iec_filename);
        exit(1);
    }
    ++cases;
}
static void status(const char *text)
{
    size=0;
    while (*text) input[size++]=(uint8_t)*text++;
    input[size-1]|=256;
}
int main(void)
{
    uint16_t i,j;
    uint8_t k,old;
    memset(src,0xa0,16); memcpy(src,"OLD",3);
    memset(dst,0xa0,16); memcpy(dst,"NEW",3);
    unit=8; op=1; status("00, OK,00,00\r");
    for(i=0;i<256;++i) { unit=i; check(src,dst); } unit=8;
    for(i=0;i<256;++i) { op=i; check(src,dst); } op=1;
    check(0,dst); check(src,0); check(src,src);
    for(k=0;k<16;++k) {
        old=src[k];
        for(i=0;i<256;++i) {src[k]=i; check(src,dst); check(dst,src);}
        src[k]=old;
    }
    for(op=1;op<=3;++op) {
        status(op==3?"01,FILES SCRATCHED,01,00\r":"00, OK,00,00\r");
        check(src,op==3?0:dst);
        for(k=0;k<4;++k) for(i=0;i<8;++i) {
            errors[k]=i; check(src,op==3?0:dst); errors[k]=0;
        }
        for(j=0;j<size;++j) {
            uint16_t value=input[j];
            for(i=0;i<514;++i) {input[j]=i; check(src,op==3?0:dst);}
            input[j]=value;
        }
        for(i=0;i<100;++i) {
            input[0]='0'+i/10; input[1]='0'+i%10;
            check(src,op==3?0:dst);
        }
    }
    printf("mutation backend: %u differential cases OK\n",cases);
    return 0;
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "udeks/cbm_mutate.h"
#include "udeks/iec_slow.h"
uint8_t reference_write_status(void), udeks_cbm_write_status(void);
uint8_t udeks_cbm_write_dos_error, busy;
extern uint8_t reference_dos_error, test_status_error, test_untalk_error;
extern uint16_t test_calls[7], test_status[80], test_size;
void test_reset(void);
uint8_t udeks_iec_poll_status(void)
{ if (busy) {--busy; return 5;} return udeks_iec_open_status(); }
static uint16_t input[80], calls[7], cases;
static uint8_t open_error, close_error, length;
static void reset(void)
{
    test_reset(); memcpy(test_status,input,sizeof(input)); test_size=length;
    test_status_error=open_error; test_untalk_error=close_error;
}
static void check(void)
{
    uint8_t expected, actual, dos;
    reset(); expected=reference_write_status(); dos=reference_dos_error;
    memcpy(calls,test_calls,sizeof(calls)); reset();
    actual=udeks_cbm_write_status();
    if (actual!=expected || dos!=udeks_cbm_write_dos_error || memcmp(calls,test_calls,sizeof(calls))) {
        printf("FAIL writer status %u: %u/%u DOS %u/%u\n", cases, expected, actual,dos,udeks_cbm_write_dos_error); exit(1);
    }
    ++cases;
}
int main(void)
{
    uint16_t i,j,original;
    const char *text="00,OK,00,00\r";
    uint8_t src[16], dst[16], result;
    length=strlen(text);
    for(i=0;i<length;++i) input[i]=text[i];
    input[length-1]|=256;
    for(j=0;j<length;++j) {
        original=input[j];
        for(i=0;i<514;++i) {input[j]=i; check();}
        input[j]=original;
    }
    for(open_error=0;open_error<5;++open_error)
        for(close_error=0;close_error<5;++close_error) check();
    open_error=close_error=0;
    memset(src,0xa0,16); src[0]='A'; memset(dst,0xa0,16); dst[0]='B';
    reset(); busy=3;
    result=udeks_cbm_mutate(8,2,src,dst);
    if (result!=11 || test_calls[1]!=1 || test_calls[5]) return 2;
    for(i=0;i<2;++i) if (udeks_cbm_mutate_poll()!=11 || test_calls[1]!=1 || test_calls[5]) return 3;
    if (udeks_cbm_mutate_poll() || test_calls[1]!=1 || test_calls[5]!=1) return 4;
    reset(); busy=1; if (udeks_cbm_mutate(8,2,src,dst)!=11) return 5;
    udeks_cbm_mutate_abort(); if (test_calls[5]!=1 || test_calls[6]) return 6;
    /* Counter exhaustion releases ownership without retransmitting DOS. */
    reset(); busy=1; if (udeks_cbm_mutate(8,2,src,dst)!=11) return 7;
    for(i=0;i<65533u;++i) { busy=1; if (udeks_cbm_mutate_poll()!=11) return 8; }
    busy=1; if (udeks_cbm_mutate_poll()!=5 || test_calls[1]!=1 || test_calls[5]!=1) return 9;
    printf("writer status: %u differential cases OK; pending/completion/abort/exhaustion OK\n",cases);
    return 0;
}

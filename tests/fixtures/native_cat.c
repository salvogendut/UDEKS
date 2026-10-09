/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/task_request.h"
#include <string.h>
volatile unsigned char native_console_request[38];
unsigned char cat_mode, cat_close_error;
unsigned int cat_size, cat_position, cat_written, cat_opens, cat_closes, cat_sleeps, cat_reads;
unsigned char cat_data[256], cat_output[256], cat_error[256];
unsigned int cat_errors;
void udeks_native_console_gate(void)
{
    volatile unsigned char *r=native_console_request;
    unsigned char op=r[7],fd=r[9],n=r[10],error=0;
    r[6]=2; r[11]=0;
    if(op==6) { ++cat_opens; r[11]=4; if(cat_mode==1) error=2; }
    else if(op==9) { ++cat_closes; error=cat_close_error; }
    else if(op==13) { ++cat_sleeps; if(cat_mode==4) error=5; }
    else if(op==1 && fd==4) {
        ++cat_reads;
        if(cat_mode==2 && cat_position) error=5;
        else {
            if(n>cat_size-cat_position) n=(unsigned char)(cat_size-cat_position);
            for(unsigned char i=0;i<n;++i) r[14+i]=cat_data[cat_position++];
            r[11]=n;
        }
    } else if(op==2 && (fd==1 || fd==2)) {
        if(fd==1 && cat_mode==3 && n) --n;
        for(unsigned char i=0;i<n;++i) {
            if(fd==1) cat_output[cat_written++]=r[14+i];
            else cat_error[cat_errors++]=r[14+i];
        }
        r[11]=n;
    } else error=22;
    if(error) { r[6]=128; r[12]=error; }
}
void cat_reset(void)
{
    cat_mode=cat_close_error=0;
    cat_size=cat_position=cat_written=cat_opens=cat_closes=cat_sleeps=cat_reads=cat_errors=0;
    memset(cat_output,0,256); memset(cat_error,0,256);
}

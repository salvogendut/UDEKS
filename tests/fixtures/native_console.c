/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
volatile unsigned char native_console_request[38];
unsigned char test_mode,test_calls,test_op,test_fd,test_count,test_sequence;
unsigned char test_payload[24],test_output[256],test_counts[64],test_fds[64];
unsigned int test_output_size;
unsigned char test_read_mode,test_input[24],test_read_count,test_poll_result=1;

void udeks_native_console_gate(void)
{
    unsigned char i;
    test_op=native_console_request[7]; test_fd=native_console_request[9];
    test_count=native_console_request[10]; test_sequence=native_console_request[8];
    test_counts[test_calls%64]=test_count; test_fds[test_calls%64]=test_fd;
    ++test_calls;
    for(i=0;i<24;++i) test_payload[i]=native_console_request[14+i];
    if(test_op==2 && test_output_size+test_count<=256) {
        memcpy(test_output+test_output_size,test_payload,test_count);
        test_output_size+=test_count;
    }
    native_console_request[6]=2;
    native_console_request[11]=test_op==2?test_count:0;
    native_console_request[12]=0;
    if(test_op==16) {
        native_console_request[11]=test_poll_result;
        native_console_request[14]=test_poll_result;
        if(test_read_mode==1) ++native_console_request[8];
        if(test_read_mode==2) native_console_request[15]=1;
        if(test_read_mode==3) ++native_console_request[16];
        if(test_read_mode==4) native_console_request[11]=2;
        if(test_read_mode==5) { native_console_request[6]=0x80; native_console_request[12]=5; }
    }
    if(test_op==1) {
        native_console_request[11]=test_read_count;
        memcpy((void *)(native_console_request+14),test_input,24);
        if(test_read_mode==6) ++native_console_request[8];
        if(test_read_mode==7) { native_console_request[6]=0x80; native_console_request[12]=11; }
    }
    if(test_mode==1) { native_console_request[6]=0x80; native_console_request[12]=5; }
    if(test_mode==2) --native_console_request[11];
    if(test_mode==3) ++native_console_request[11];
    if(test_mode==4) ++native_console_request[8];
    if(test_mode==5) ++native_console_request[7];
    if(test_mode==6) ++native_console_request[9];
    if(test_mode==7) ++native_console_request[10];
    if(test_mode==8) native_console_request[13]=1;
    if(test_mode==9) native_console_request[6]=1;
    if(test_mode==10) native_console_request[6]=0x80; /* error without errno */
    if(test_mode==11) native_console_request[12]=5;  /* success with errno */
    if(test_mode==12) native_console_request[0]=0;
}

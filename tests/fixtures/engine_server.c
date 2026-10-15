/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include <setjmp.h>
#define ENGINE_SERVER_HOST_TEST
#include "../../user/services/engine/server.c"
volatile unsigned char udeks_native_console_record[38],udeks_worker_output[64],udeks_worker_mailbox[64];
unsigned char udeks_errno,engine_test_mode;
unsigned int engine_test_worker_calls,engine_test_receive_calls,engine_test_reply_count,engine_test_sleeps,engine_test_closes,engine_test_sends;
unsigned char engine_test_replies[16][16],engine_test_lengths[16];
static jmp_buf worker_return;
static unsigned char step,timeout_recovered;
extern void z80_main(void);
void udeks_z80_yield(void) { longjmp(worker_return,1); }
unsigned char udeks_native_request_version(unsigned char operation,unsigned char fd,unsigned char count,unsigned char minor)
{
    unsigned char n=P[3];
    (void)operation;(void)fd;(void)count;(void)minor;++engine_test_worker_calls;
    memset((void *)udeks_worker_mailbox,0,64);memcpy((void *)udeks_worker_mailbox,"UDEK",4);
    udeks_worker_mailbox[5]=3;udeks_worker_mailbox[6]=1;udeks_worker_mailbox[7]=P[0];
    udeks_worker_mailbox[12]=P[1];udeks_worker_mailbox[14]=P[2];udeks_worker_mailbox[16]=n;
    if(!setjmp(worker_return))z80_main();
    P[0]=udeks_worker_mailbox[18];P[1]=udeks_worker_mailbox[19];P[2]=n;
    udeks_errno=0;return 3;
}
udeks_ipc_handle udeks_ipc_create(const unsigned char *name) { (void)name;return 123; }
unsigned char udeks_ipc_close(udeks_ipc_handle endpoint) { (void)endpoint;++engine_test_closes;return 0; }
unsigned char udeks_sleep(unsigned int ticks) { (void)ticks;++engine_test_sleeps;return 0; }
unsigned char udeks_write_bytes(unsigned char fd,const unsigned char *data,unsigned char count) { (void)fd;(void)data;return count; }
unsigned char udeks_ipc_send(udeks_ipc_handle peer,udeks_ipc_handle endpoint,const unsigned char *data,unsigned char count)
{
    (void)peer;(void)endpoint;++engine_test_sends;
    if(engine_test_mode==2 && engine_test_reply_count==1) {
        /* Retired peer before accepting this wave reply; only once. */
        engine_test_mode=0;udeks_errno=9;return 255;
    }
    if(engine_test_mode==3 && engine_test_sends<=2) { udeks_errno=11;return 255; }
    memcpy(engine_test_replies[engine_test_reply_count],data,count);engine_test_lengths[engine_test_reply_count++]=count;
    /* Simulate another user of the borrowed worker bytes after IPC starts. */
    memset((void *)udeks_worker_output,0xcc,64);udeks_errno=0;return 0;
}
unsigned char udeks_ipc_receive(udeks_ipc_handle endpoint,udeks_ipc_handle *sender,unsigned char *data,unsigned char capacity)
{
    unsigned char n=8;
    (void)endpoint;(void)capacity;++engine_test_receive_calls;*sender=64;
    memset(data,0,16);data[0]=1;data[1]=1;data[2]=step+1;
    if(engine_test_mode==1 && step>=9) {
        if(!timeout_recovered && engine_server_state==2) { data[1]=4;data[2]=10;return 8; }
        if(!timeout_recovered) { timeout_recovered=1;data[1]=3;data[2]=99;return 8; }
        data[1]=4;data[2]=99;return 8;
    }
    switch(step) {
    case 1:data[4]=4;data[5]=250;data[6]=7;data[7]=8;break;
    case 2:data[4]=4;data[7]=9;break;
    case 3:data[1]=3;data[5]=1;break;
    case 5:n=4;break;
    case 6:data[4]=5;data[6]=1;data[7]=25;break;
    case 7:data[1]=4;break;
    case 8:data[1]=3;break;
    case 9:data[1]=4;data[2]=9;*sender=65;break;
    case 10:data[1]=4;data[2]=10;break;
    case 11:data[1]=4;data[2]=9;data[4]=1;break;
    default:if(step>=12) { data[1]=4;data[2]=9; }break;
    }
    ++step;udeks_errno=0;return n;
}
unsigned char engine_test_run(unsigned char mode)
{
    engine_test_mode=mode;step=0;timeout_recovered=0;stopping=0;stop_lo=0;stop_hi=0;
    engine_server_jobs=0;engine_server_error=0;engine_server_state=0;
    engine_test_worker_calls=0;engine_test_receive_calls=0;engine_test_reply_count=0;
    engine_test_sleeps=0;engine_test_closes=0;engine_test_sends=0;udeks_errno=0;
    memset(packet,0,16);memset(engine_test_replies,0,256);memset(engine_test_lengths,0,16);
    return udeks_program_main(1,0);
}

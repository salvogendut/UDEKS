/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include <setjmp.h>
#include "../../bench/engine/bounds_client.c"
#include "../../user/services/engine/protocol.h"
unsigned char udeks_errno;
volatile unsigned char udeks_worker_mailbox[64],udeks_worker_output[64];
unsigned int engine_bounds_worker_calls,engine_bounds_closed;
static unsigned char response[16],response_length;
static jmp_buf completed;
extern void z80_main(void);
void udeks_z80_yield(void) { longjmp(completed,1); }
udeks_ipc_handle udeks_ipc_lookup(const unsigned char *name) { (void)name;return 10; }
udeks_ipc_handle udeks_ipc_create(const unsigned char *name) { (void)name;return 11; }
unsigned char udeks_ipc_close(udeks_ipc_handle handle) { (void)handle;++engine_bounds_closed;return 0; }
unsigned char udeks_sleep(unsigned int ticks) { (void)ticks;return 0; }
unsigned char udeks_ipc_send(udeks_ipc_handle destination,udeks_ipc_handle source,const unsigned char *data,unsigned char size)
{
    unsigned char error=engine_validate(data,size),n=0;
    (void)destination;(void)source;
    memset(response,0,sizeof(response));response[0]=1;response[1]=2;response[2]=data[2];response[3]=data[3];response[4]=error;
    if(!error) {
        ++engine_bounds_worker_calls;n=data[7];
        memset((void *)udeks_worker_mailbox,0,64);memcpy((void *)udeks_worker_mailbox,"UDEK",4);
        udeks_worker_mailbox[5]=3;udeks_worker_mailbox[6]=1;udeks_worker_mailbox[7]=data[4];
        udeks_worker_mailbox[12]=data[5];udeks_worker_mailbox[14]=data[6];udeks_worker_mailbox[16]=n;
        if(!setjmp(completed))z80_main();
        response[5]=udeks_worker_mailbox[18];response[6]=udeks_worker_mailbox[19];response[7]=n;
        memcpy(response+8,(const void *)udeks_worker_output,n);
    }
    response_length=8+n;return 0;
}
unsigned char udeks_ipc_receive(udeks_ipc_handle handle,udeks_ipc_handle *sender,unsigned char *data,unsigned char capacity)
{
    (void)handle;(void)capacity;*sender=10;memcpy(data,response,response_length);return response_length;
}
unsigned char engine_bounds_run(void)
{
    memset(packet,0,16);sequence=phase=step=count=0;
    engine_bounds_state=engine_bounds_error=0;engine_bounds_checks=0;engine_bounds_worker_calls=engine_bounds_closed=0;
    return udeks_program_main(1,0);
}

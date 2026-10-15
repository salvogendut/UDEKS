/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <setjmp.h>
#include <string.h>
#include "../../user/services/engine/protocol.h"
volatile unsigned char udeks_worker_mailbox[64],udeks_worker_output[64];
static jmp_buf completed;
extern void z80_main(void);
void udeks_z80_yield(void) { longjmp(completed,1); }
unsigned char engine_test_validate(const unsigned char *p,unsigned char count)
{ return engine_validate(p,count); }
void engine_test_worker(unsigned char op,unsigned char a,unsigned char b,unsigned char count)
{
    memset((void *)udeks_worker_mailbox,0,64);
    memset((void *)udeks_worker_output,0xa5,64);
    memcpy((void *)udeks_worker_mailbox,"UDEK",4);
    udeks_worker_mailbox[5]=3;udeks_worker_mailbox[6]=1;
    udeks_worker_mailbox[7]=op;udeks_worker_mailbox[12]=a;
    udeks_worker_mailbox[14]=b;udeks_worker_mailbox[16]=count;
    if(!setjmp(completed))z80_main();
}

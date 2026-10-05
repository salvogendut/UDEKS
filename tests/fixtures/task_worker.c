/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <setjmp.h>
#include <string.h>
volatile unsigned char udeks_graphics_record[38],udeks_worker_mailbox[64];
volatile unsigned char udeks_worker_status[32],udeks_worker_boot_chain[16];
volatile unsigned char udeks_worker_output[64];
unsigned int test_calls;
unsigned char test_fault,test_busy;
static jmp_buf worker_yield;
#include "../../src/services/engine/z80_worker.c"
#include "../../src/services/engine/task_worker.c"
#undef MAILBOX_BYTE
#define UDEKS_Z80_WORKER_HOST_TEST
#include "../../src/z80/worker.c"

void udeks_z80_prepare(void) {}
void udeks_z80_yield(void) { longjmp(worker_yield,1); }
void udeks_z80_handoff(void) {
    ++test_calls;
    if(!setjmp(worker_yield)) z80_main();
    if(test_fault==1) ++udeks_worker_mailbox[8];
    if(test_fault==2) udeks_worker_mailbox[6]=0;
}
void udeks_z80_increment_counter(unsigned char n) {
    if(!++udeks_worker_status[n]) ++udeks_worker_status[n+1];
}
void udeks_vic_pointer_busy_begin(unsigned char reason) { (void)reason; ++test_busy; }
void udeks_vic_pointer_busy_end(unsigned char reason) { (void)reason; --test_busy; }
void test_reset(void) {
    memset((void *)udeks_graphics_record,0,38);
    memset((void *)udeks_worker_mailbox,0,64);
    memset((void *)udeks_worker_output,0xa5,64);
    memcpy((void *)udeks_worker_boot_chain,"S0OKS1OKZ80!\x02\0",14);
    memcpy((void *)udeks_worker_mailbox,"UDEK\0\x03",6);
    sequence=0; test_calls=0; test_fault=0; test_busy=0;
    udeks_z80_worker_start();
    test_calls=0;
}
/* Model only the existing assembly reply tail; policy/transport/math above
 * are the production C translation units, not a second implementation. */
unsigned char test_request(void) {
    unsigned char error=udeks_task_worker_request();
    udeks_graphics_record[11]=error?0:3;
    udeks_graphics_record[12]=error;
    udeks_graphics_record[6]=error?0x80:2;
    return error;
}

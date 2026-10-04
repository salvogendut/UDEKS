/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent native console/task client: no window, app id or UAPP import. */
#include "worker.h"
extern volatile unsigned char udeks_graphics_record[38];
extern void gfx_sleep(void);
#define R udeks_graphics_record
#define P (udeks_graphics_record+14)
unsigned char worker_command,worker_state,worker_failure,worker_steps;
unsigned char worker_samples[525],worker_wave[64],worker_phase;
static unsigned char row,i,sequence;

static unsigned char request(unsigned char op,unsigned char a,unsigned char b,unsigned char n)
{
    P[0]=op; P[1]=a; P[2]=b; P[3]=n;
    sequence=R[8]+1;
    i=worker_request();
    if(R[8]!=sequence) { worker_failure=1; return 255; }
    return i;
}

unsigned char udeks_graphical_main(void)
{
    worker_state=1;
    while(!worker_command) gfx_sleep();
    /* Envelope and operand errors must return without stranding the caller. */
    if(request(1,0,0,0)!=38 || request(4,0,0,65)!=22 ||
       request(5,20,2,50)!=22 || request(0,0,0,0) || P[2]) {
        worker_failure=2; goto failed;
    }
    worker_state=2;
    for(row=0;row<21;++row) {
        if(request(5,row,1,25) || P[0]!=row+1 || P[1] || P[2]!=25) {
            worker_failure=3; goto failed;
        }
        for(i=0;i<25;++i) worker_samples[(unsigned int)row*25u+i]=udeks_worker_output[i];
        ++worker_steps;
        gfx_sleep();
    }
    worker_phase=(unsigned int)worker_wave>>8;
    if(request(4,worker_phase,7,64) || P[0]!=(unsigned char)(worker_phase+64u*7u) || P[1] || P[2]!=64) {
        worker_failure=4; goto failed;
    }
    for(i=0;i<64;++i) worker_wave[i]=udeks_worker_output[i];
    worker_state=3;
    while(worker_command!=2) gfx_sleep();
    return 0;
failed:
    worker_state=0x80;
    for(;;) gfx_sleep();
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Machine qualification only: frozen legacy waveform, raw protocol bounds. */
#include "udeks/native_console.h"
#include "udeks/native_ipc.h"
#include "udeks/task_request.h"
unsigned char engine_bounds_state,engine_bounds_error;
unsigned int engine_bounds_checks;
static unsigned char packet[16],sequence,phase,step,count;
static udeks_ipc_handle endpoint,peer;
static const signed char wave[64]={
 0,3,6,9,12,14,17,19,21,23,25,26,28,29,29,30,
 30,30,29,29,28,26,25,23,21,19,17,14,12,9,6,3,
 0,-3,-6,-9,-12,-14,-17,-19,-21,-23,-25,-26,-28,-29,-29,-30,
 -30,-30,-29,-29,-28,-26,-25,-23,-21,-19,-17,-14,-12,-9,-6,-3};
static const unsigned char phases[3]={0,250,255},steps[4]={0,1,7,255};
static unsigned char exchange(unsigned char kind,unsigned char op,unsigned char n,unsigned char error)
{
    unsigned int waited;
    unsigned char length,i,next=phase;
    udeks_ipc_handle sender;
    packet[0]=1;packet[1]=kind;packet[2]=++sequence;packet[3]=0;
    packet[4]=op;packet[5]=phase;packet[6]=step;packet[7]=count;
    for(waited=0;waited<600;++waited) {
        if(!udeks_ipc_send(peer,endpoint,packet,n))break;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1))return udeks_errno;
    }
    if(waited==600)return UDEKS_TREQ_EAGAIN;
    for(waited=0;waited<600;++waited) {
        length=udeks_ipc_receive(endpoint,&sender,packet,16);
        if(length!=UDEKS_IO_ERROR)break;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1))return udeks_errno;
    }
    if(waited==600)return UDEKS_TREQ_EAGAIN;
    if(sender!=peer || packet[0]!=1 || packet[1]!=2 || packet[2]!=sequence || packet[3] ||
       packet[4]!=error || packet[6])return UDEKS_TREQ_EPROTO;
    if(error || op==0) {
        if(length!=8 || packet[5] || packet[7])return UDEKS_TREQ_EPROTO;
    } else {
        if(length!=8+count || packet[7]!=count)return UDEKS_TREQ_EPROTO;
        for(i=0;i<count;++i) {
            if(packet[8+i]!=(unsigned char)wave[next>>2])return UDEKS_TREQ_EPROTO;
            next+=step;
        }
        if(packet[5]!=next)return UDEKS_TREQ_EPROTO;
    }
    ++engine_bounds_checks;return 0;
}
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned char a,b,error;
    (void)argc;(void)argv;
    engine_bounds_state=1;
    peer=udeks_ipc_lookup((const unsigned char *)"engine");
    if(!peer) { engine_bounds_error=udeks_errno;return udeks_errno; }
    endpoint=udeks_ipc_create((const unsigned char *)"engcheck");
    if(!endpoint) { engine_bounds_error=udeks_errno;return udeks_errno; }
    error=exchange(1,0,8,0);if(error)goto done;
    for(a=0;a<3;++a)for(b=0;b<4;++b)for(count=1;count<=8;++count) {
        phase=phases[a];step=steps[b];
        error=exchange(1,4,8,0);if(error)goto done;
    }
    phase=0;step=1;count=0;error=exchange(1,4,8,22);if(error)goto done;
    count=9;error=exchange(1,4,8,22);if(error)goto done;
    count=8;error=exchange(1,5,8,38);if(error)goto done;
    error=exchange(1,255,8,38);if(error)goto done;
    error=exchange(3,4,8,22);if(error)goto done; /* Invalid STOP must not stop. */
    error=exchange(1,4,7,71);if(error)goto done;
    error=exchange(2,4,8,71);
done:
    if(udeks_ipc_close(endpoint) && !error)error=udeks_errno;
    engine_bounds_error=error;engine_bounds_state=error?3:2;
    return error;
}

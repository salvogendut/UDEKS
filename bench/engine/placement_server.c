/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Link-size probe only: not a runnable server or a delivery image. */
#include "udeks/native_console.h"
#include "udeks/native_ipc.h"
#include "udeks/task_request.h"
#include "../../user/services/engine/protocol.h"
extern unsigned char udeks_native_request_version(unsigned char,unsigned char,unsigned char,unsigned char);
extern volatile unsigned char udeks_native_console_record[38];
#define P (udeks_native_console_record+14)
#define OUTPUT ((volatile unsigned char *)0xf300u)
static unsigned char packet[16],samples[8];
static udeks_ipc_handle endpoint,peer;
static unsigned int result;
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned char n,error,i,op;
    unsigned int attempts;
    (void)argc;(void)argv;
    endpoint=udeks_ipc_create((const unsigned char *)"engine");
    if(!endpoint)return udeks_errno;
    n=udeks_ipc_receive(endpoint,&peer,packet,16);
    if(n==255)return udeks_errno;
    error=engine_validate(packet,n);op=packet[4];n=packet[7];
    if(!error && packet[1]==ENGINE_REQUEST) {
        for(i=0;i<4;++i)P[i]=packet[4+i];
        if(udeks_native_request_version(24,0,4,11)!=3)error=udeks_errno?udeks_errno:UDEKS_TREQ_EPROTO;
        else if(P[2]!=n)error=UDEKS_TREQ_EPROTO;
        else {
            result=P[0]|((unsigned int)P[1]<<8);
            /* Borrowed output copied before IPC, sleep or any other gate. */
            for(i=0;i<n;++i)samples[i]=OUTPUT[i];
        }
    }
    packet[0]=1;packet[1]=ENGINE_REPLY;packet[4]=error;
    packet[5]=error?0:(unsigned char)result;packet[6]=error?0:(unsigned char)(result>>8);
    packet[7]=(!error && op==4)?n:0;
    for(i=0;i<packet[7];++i)packet[8+i]=samples[i];
    for(attempts=0;attempts<ENGINE_WAIT;++attempts) {
        if(!udeks_ipc_send(peer,endpoint,packet,8+packet[7]))break;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN)return udeks_errno;
        if(udeks_sleep(1))return udeks_errno;
    }
    /* Force lifecycle/diagnostic dependencies into the size measurement.
     * Slice 2 must implement reply consumption and STOP/ACK before retirement. */
    udeks_write(UDEKS_STDOUT,(const unsigned char *)"engine placement only\n");
    return udeks_ipc_close(endpoint);
}

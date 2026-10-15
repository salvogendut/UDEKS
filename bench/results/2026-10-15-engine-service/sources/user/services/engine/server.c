/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/native_console.h"
#include "udeks/native_ipc.h"
#include "udeks/task_request.h"
#define ENGINE_INLINE_PACKET_VALIDATION
#include "protocol.h"
extern unsigned char udeks_native_request_version(unsigned char,unsigned char,unsigned char,unsigned char);
extern volatile unsigned char udeks_native_console_record[38];
#define P (udeks_native_console_record+14)
#ifdef ENGINE_SERVER_HOST_TEST
extern volatile unsigned char udeks_worker_output[64];
#define OUTPUT udeks_worker_output
#else
#define OUTPUT ((volatile unsigned char *)0xf300u)
#endif
unsigned char engine_server_state,engine_server_error;
unsigned int engine_server_jobs;
udeks_ipc_handle engine_server_handle;
static unsigned char packet[16],stop_lo,stop_hi;
static udeks_ipc_handle stopping;
static unsigned char failure(unsigned char error)
{
    engine_server_error=error;
    udeks_write_bytes(UDEKS_STDERR,(const unsigned char *)"engine: error\n",14);
    return error?error:1;
}
static unsigned char reply(udeks_ipc_handle peer,unsigned char n)
{
    unsigned int waited;
    for(waited=0;waited<ENGINE_WAIT;++waited) {
        if(!udeks_ipc_send(peer,engine_server_handle,packet,n))return 0;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1))return udeks_errno;
    }
    return UDEKS_TREQ_EAGAIN;
}
static unsigned char work(void)
{
    unsigned char i,n=packet[7];
    for(i=0;i<4;++i)P[i]=packet[4+i];
    if(udeks_native_request_version(UDEKS_TREQ_OP_WORKER,0,4,11)!=3)
        return udeks_errno?udeks_errno:UDEKS_TREQ_EPROTO;
    if(P[2]!=n || P[1] || (!n && P[0]))return UDEKS_TREQ_EPROTO;
    /* Snapshot borrowed bytes before IPC, sleep or any further syscall. */
    for(i=0;i<n;++i)packet[8+i]=OUTPUT[i];
    packet[5]=P[0];packet[6]=P[1];return 0;
}
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    udeks_ipc_handle peer;
    unsigned int waited=0;
    unsigned char n,error,kind;
    (void)argv;
    if(argc!=1)return 2;
    engine_server_handle=udeks_ipc_create((const unsigned char *)"engine");
    if(!engine_server_handle)return failure(udeks_errno);
    engine_server_state=1;
    udeks_write_bytes(UDEKS_STDOUT,(const unsigned char *)"engine: ready\n",14);
    for(;;) {
        n=udeks_ipc_receive(engine_server_handle,&peer,packet,16);
        if(n==UDEKS_IO_ERROR && udeks_errno!=UDEKS_TREQ_EAGAIN)return failure(udeks_errno);
        if(stopping) {
            if(n==8 && packet[0]==1 && packet[1]==ENGINE_ACK &&
               !(packet[4]|packet[5]|packet[6]|packet[7]) &&
               peer==stopping && packet[2]==stop_lo && packet[3]==stop_hi)break;
            if(udeks_sleep(1))return failure(udeks_errno);
            if(++waited==ENGINE_WAIT) { stopping=0;engine_server_state=1; }
            continue;
        }
        if(n==UDEKS_IO_ERROR) { if(udeks_sleep(1))return failure(udeks_errno);continue; }
        if(n<4 || packet[0]!=1 || !(packet[2]|packet[3]))continue;
        error=ENGINE_VALIDATE(packet,n);kind=packet[1];
        if(!error && kind==ENGINE_ACK)continue;
        if(!error && kind==ENGINE_REQUEST) {
            engine_server_state=3;error=work();if(!error)++engine_server_jobs;
        } else if(!error) { packet[5]=0;packet[6]=0; }
        if(error)kind=ENGINE_REQUEST; /* An error reply must never arm STOP. */
        packet[0]=1;packet[1]=ENGINE_REPLY;packet[4]=error;
        if(error) { packet[5]=0;packet[6]=0;packet[7]=0; }
        error=reply(peer,8+packet[7]);engine_server_state=1;
        if(!error && kind==ENGINE_STOP) {
            stopping=peer;stop_lo=packet[2];stop_hi=packet[3];waited=0;engine_server_state=2;
        }
        if(error && error!=UDEKS_TREQ_EBADF && error!=UDEKS_TREQ_EAGAIN)return failure(error);
    }
    if(udeks_ipc_close(engine_server_handle))return failure(udeks_errno);
    engine_server_state=4;
    return 0;
}

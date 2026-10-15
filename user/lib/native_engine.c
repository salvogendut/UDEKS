/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/native_engine.h"
#include "udeks/native_ipc.h"
#include "udeks/task_request.h"
#define ENGINE_INLINE_PACKET_VALIDATION
#include "../services/engine/protocol.h"
static unsigned char packet[16];
static unsigned int sequence;
static udeks_ipc_handle peer,endpoint;
static unsigned char count,stop_request;
static unsigned char *samples;
static unsigned int *result;
static unsigned char failure(unsigned char error)
{ udeks_errno=error;return UDEKS_IO_ERROR; }
static unsigned char send(unsigned char n)
{
    unsigned int waited;
    for(waited=0;waited<ENGINE_WAIT;++waited) {
        if(!udeks_ipc_send(peer,endpoint,packet,n))return 0;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1))return udeks_errno;
    }
    return UDEKS_TREQ_EAGAIN;
}
static unsigned char exchange(void)
{
    udeks_ipc_handle sender,found;
    unsigned char error=0,n,i;
    unsigned int waited;
    peer=udeks_ipc_lookup((const unsigned char *)"engine");
    if(!peer)return UDEKS_IO_ERROR;
    endpoint=udeks_ipc_create((const unsigned char *)"engreply");
    if(!endpoint)return UDEKS_IO_ERROR;
    if(!++sequence)++sequence;
    packet[0]=1;packet[2]=(unsigned char)sequence;packet[3]=(unsigned char)(sequence>>8);
    error=send(8);if(error)goto cleanup;
    for(waited=0;waited<ENGINE_WAIT;++waited) {
        n=udeks_ipc_receive(endpoint,&sender,packet,16);
        if(n!=UDEKS_IO_ERROR)break;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1)) { error=udeks_errno;goto cleanup; }
    }
    if(waited==ENGINE_WAIT) { error=UDEKS_TREQ_EAGAIN;goto cleanup; }
    if(sender!=peer || n<8 || packet[0]!=1 || packet[1]!=ENGINE_REPLY ||
       packet[2]!=(unsigned char)sequence || packet[3]!=(unsigned char)(sequence>>8))goto protocol;
    if(packet[4]) {
        if(packet[4]==255 || n!=8 || packet[5] || packet[6] || packet[7])goto protocol;
        error=packet[4];goto cleanup;
    }
    if(n!=8+count || packet[7]!=count || packet[6] || (!count && packet[5]))goto protocol;
    if(!count && packet[1]==ENGINE_REPLY && stop_request) {
        packet[1]=ENGINE_ACK;
        for(i=4;i<8;++i)packet[i]=0;
        error=send(8);if(error)goto cleanup;
        for(waited=0;waited<ENGINE_WAIT;++waited) {
            found=udeks_ipc_lookup((const unsigned char *)"engine");
            if((!found && udeks_errno==UDEKS_TREQ_ENOENT) || (found && found!=peer))break;
            if(!found || udeks_sleep(1)) { error=udeks_errno;goto cleanup; }
        }
        if(waited==ENGINE_WAIT)error=UDEKS_TREQ_EAGAIN;
    }
    /* Endpoint close must also succeed before changing caller outputs. */
cleanup:
    if(udeks_ipc_close(endpoint) && !error)error=udeks_errno;
    if(error)return failure(error);
    for(i=0;i<count;++i)samples[i]=packet[8+i];
    if(result)*result=packet[5];
    udeks_errno=0;return 0;
protocol:
    error=UDEKS_TREQ_EPROTO;goto cleanup;
}
unsigned char udeks_engine_wave(unsigned char a,unsigned char b,unsigned char n,
                               unsigned char *buffer,unsigned int *next_phase)
{
    if(!n || n>8 || !buffer || !next_phase)return failure(UDEKS_TREQ_EINVAL);
    packet[1]=ENGINE_REQUEST;packet[4]=4;packet[5]=a;packet[6]=b;packet[7]=n;
    count=n;stop_request=0;samples=buffer;result=next_phase;
    return exchange();
}
static unsigned char control(unsigned char action)
{
    packet[1]=action;packet[4]=0;packet[5]=0;packet[6]=0;packet[7]=0;
    stop_request=action==ENGINE_STOP;count=0;samples=0;result=0;
    return exchange();
}
unsigned char udeks_engine_nop(void) { return control(ENGINE_REQUEST); }
unsigned char udeks_engine_stop(void) { return control(ENGINE_STOP); }

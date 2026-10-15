/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Test-only raw SDK peer. Never ACK a successful STOP: either retire the
 * reply endpoint immediately, or wait for foreground server cancellation. */
#include "udeks/native_console.h"
#include "udeks/native_ipc.h"
#include "udeks/task_request.h"
unsigned char engine_peer_state,engine_peer_error,engine_peer_stale;
udeks_ipc_handle engine_peer_handle,engine_peer_server;
static unsigned char packet[16];
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned int waited;
    unsigned char n,error=0;
    udeks_ipc_handle sender,found;
    (void)argv;
    engine_peer_handle=udeks_ipc_create((const unsigned char *)"engreply");
    if(!engine_peer_handle)return udeks_errno;
    engine_peer_state=1;
    for(waited=0;waited<600;++waited) {
        engine_peer_server=udeks_ipc_lookup((const unsigned char *)"engine");
        if(engine_peer_server)break;
        if(udeks_errno!=UDEKS_TREQ_ENOENT || udeks_sleep(1)) { error=udeks_errno;goto done; }
    }
    if(!engine_peer_server) { error=UDEKS_TREQ_EAGAIN;goto done; }
    packet[0]=1;packet[1]=3;packet[2]=1;
    if(udeks_ipc_send(engine_peer_server,engine_peer_handle,packet,8)) { error=udeks_errno;goto done; }
    for(waited=0;waited<600;++waited) {
        n=udeks_ipc_receive(engine_peer_handle,&sender,packet,16);
        if(n!=UDEKS_IO_ERROR)break;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1)) { error=udeks_errno;goto done; }
    }
    if(waited==600) { error=UDEKS_TREQ_EAGAIN;goto done; }
    if(n!=8 || sender!=engine_peer_server || packet[0]!=1 || packet[1]!=2 ||
       packet[2]!=1 || packet[3] || packet[4] || packet[5] || packet[6] || packet[7]) {
        error=UDEKS_TREQ_EPROTO;goto done;
    }
    engine_peer_state=2;
    if(argc==2)goto done; /* Abandon a reply after consuming it, without ACK. */
    for(waited=0;waited<600;++waited) {
        found=udeks_ipc_lookup((const unsigned char *)"engine");
        if(!found && udeks_errno==UDEKS_TREQ_ENOENT)break;
        if(found!=engine_peer_server || udeks_sleep(1)) { error=UDEKS_TREQ_EPROTO;goto done; }
    }
    if(waited==600) { error=UDEKS_TREQ_EAGAIN;goto done; }
    if(!udeks_ipc_send(engine_peer_server,engine_peer_handle,packet,8))error=UDEKS_TREQ_EPROTO;
    engine_peer_stale=udeks_errno;
    if(engine_peer_stale!=UDEKS_TREQ_EBADF)error=UDEKS_TREQ_EPROTO;
done:
    if(udeks_ipc_close(engine_peer_handle) && !error)error=udeks_errno;
    engine_peer_error=error;engine_peer_state=3;
    return error;
}

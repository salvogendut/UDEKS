/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Link-size probe only; runtime authentication/lifecycle belongs to slice 2. */
#include "udeks/native_console.h"
#include "udeks/native_ipc.h"
#include "../../user/services/engine/protocol.h"
static unsigned char packet[16]={1,1,1,0,4,250,7,8};
static udeks_ipc_handle endpoint,peer,sender;
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned int attempts;
    unsigned char n;
    (void)argc;(void)argv;
    peer=udeks_ipc_lookup((const unsigned char *)"engine");
    if(!peer)return udeks_errno;
    endpoint=udeks_ipc_create((const unsigned char *)"engreply");
    if(!endpoint)return udeks_errno;
    for(attempts=0;attempts<ENGINE_WAIT;++attempts) {
        if(!udeks_ipc_send(peer,endpoint,packet,8))break;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1))return udeks_errno;
    }
    for(attempts=0;attempts<ENGINE_WAIT;++attempts) {
        n=udeks_ipc_receive(endpoint,&sender,packet,16);
        if(n!=255)break;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1))return udeks_errno;
    }
    udeks_write(UDEKS_STDOUT,(const unsigned char *)"engine placement only\n");
    return udeks_ipc_close(endpoint);
}

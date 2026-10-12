/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Qualification peer: start before the foreground server, then prove that
 * cancelling it leaves a bounded receive failure and no owned resources. */
#include "udeks/native_console.h"
#include "udeks/native_ipc.h"
#include "udeks/task_request.h"
unsigned char ipc_orphan_state,ipc_orphan_error,ipc_orphan_stale;
udeks_ipc_handle ipc_orphan_handle,ipc_orphan_peer;
static unsigned char packet[16]={1,'g','o','n','e'};
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned int attempts;
    unsigned char count,rc=0;
    udeks_ipc_handle sender;
    (void)argc;(void)argv;
    ipc_orphan_handle=udeks_ipc_create((const unsigned char *)"reply");
    if(!ipc_orphan_handle) { ipc_orphan_error=udeks_errno;return udeks_errno; }
    ipc_orphan_state=1;
    for(attempts=0;attempts<600;++attempts) {
        ipc_orphan_peer=udeks_ipc_lookup((const unsigned char *)"echo");
        if(ipc_orphan_peer)break;
        if(udeks_errno!=UDEKS_TREQ_ENOENT || udeks_sleep(1)) { rc=udeks_errno;goto done; }
    }
    if(!ipc_orphan_peer) { rc=UDEKS_TREQ_EAGAIN;goto done; }
    if(udeks_ipc_send(ipc_orphan_peer,ipc_orphan_handle,packet,5)) { rc=udeks_errno;goto done; }
    ipc_orphan_state=2;
    for(attempts=0;attempts<600;++attempts) {
        count=udeks_ipc_receive(ipc_orphan_handle,&sender,packet,sizeof(packet));
        if(count!=UDEKS_IO_ERROR) { rc=UDEKS_TREQ_EPROTO;goto done; }
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1)) { rc=udeks_errno;goto done; }
    }
    rc=UDEKS_TREQ_EAGAIN;
    if(!udeks_ipc_send(ipc_orphan_peer,ipc_orphan_handle,packet,5))rc=UDEKS_TREQ_EPROTO;
    ipc_orphan_stale=udeks_errno;
    if(ipc_orphan_stale!=UDEKS_TREQ_EBADF)rc=UDEKS_TREQ_EPROTO;
done:
    if(udeks_ipc_close(ipc_orphan_handle) && !rc)rc=udeks_errno;
    ipc_orphan_error=rc;ipc_orphan_state=3;
    return rc;
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/native_console.h"
#include "udeks/native_ipc.h"
#include "udeks/task_request.h"
#include "protocol.h"
unsigned char ipc_server_state,ipc_server_error;
unsigned int ipc_server_count;
udeks_ipc_handle ipc_server_handle;
static unsigned char packet[UDEKS_IPC_MESSAGE_MAX];
static unsigned char failure(unsigned char error)
{
    ipc_server_error=error;
    udeks_write(UDEKS_STDERR,(const unsigned char *)"ipcsrv: IPC error\n");
    return error?error:1;
}
static unsigned char reply(udeks_ipc_handle peer,unsigned char count)
{
    unsigned int attempts;
    for(attempts=0;attempts<IPC_DEMO_WAIT;++attempts) {
        if(!udeks_ipc_send(peer,ipc_server_handle,packet,count))return 0;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN)return udeks_errno;
        if(udeks_sleep(1))return udeks_errno;
    }
    return UDEKS_TREQ_EAGAIN;
}
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    const unsigned char *name=(const unsigned char *)"echo";
    udeks_ipc_handle peer,stopping=0;
    unsigned char count,i,error;
    unsigned int waited=0;
    if(argc>2) { udeks_write(UDEKS_STDERR,(const unsigned char *)"ipcsrv [endpoint]\n");return 2; }
    if(argc==2)name=argv[1];
    ipc_server_handle=udeks_ipc_create(name);
    if(!ipc_server_handle)return failure(udeks_errno);
    ipc_server_state=1;
    udeks_write(UDEKS_STDOUT,(const unsigned char *)"ipcsrv: ready\n");
    for(;;) {
        count=udeks_ipc_receive(ipc_server_handle,&peer,packet,sizeof(packet));
        if(count==UDEKS_IO_ERROR) {
            if(udeks_errno!=UDEKS_TREQ_EAGAIN)return failure(udeks_errno);
            if(stopping && ++waited==IPC_DEMO_WAIT) { stopping=0;ipc_server_state=1; }
            if(udeks_sleep(1))return failure(udeks_errno);
            continue;
        }
        if(stopping) {
            if(peer==stopping && count==1 && packet[0]==IPC_DEMO_ACK)break;
            continue;
        }
        if(count==1 && packet[0]==IPC_DEMO_STOP) {
            packet[0]=IPC_DEMO_STOPPED;error=reply(peer,1);
            if(!error) { stopping=peer;waited=0;ipc_server_state=2; }
        } else if(count>=2 && packet[0]==IPC_DEMO_DATA) {
            /* Deliberate demo work interval: private request bytes survive
             * a sleep while the client, shell and graphical peers run. */
            ipc_server_state=4;
            if(udeks_sleep(60))return failure(udeks_errno);
            for(i=1;i<count;++i) if(packet[i]>='a' && packet[i]<='z')packet[i]-='a'-'A';
            packet[0]=IPC_DEMO_REPLY;error=reply(peer,count);
            if(!error)++ipc_server_count;
            ipc_server_state=1;
        } else continue;
        /* A cancelled client can vanish before the reply; keep serving. */
        if(error && error!=UDEKS_TREQ_EBADF && error!=UDEKS_TREQ_EAGAIN)return failure(error);
    }
    if(udeks_ipc_close(ipc_server_handle))return failure(udeks_errno);
    ipc_server_state=3;
    udeks_write(UDEKS_STDOUT,(const unsigned char *)"ipcsrv: stopped\n");
    return 0;
}

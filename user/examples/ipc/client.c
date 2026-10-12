/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/native_console.h"
#include "udeks/native_ipc.h"
#include "udeks/task_request.h"
#include "protocol.h"
#include <string.h>
unsigned char ipc_client_state,ipc_client_error,ipc_client_count;
unsigned char ipc_client_reply[UDEKS_IPC_MESSAGE_MAX];
udeks_ipc_handle ipc_client_handle,ipc_client_peer;
static unsigned char error(unsigned char code)
{
    ipc_client_error=code;
    udeks_write(UDEKS_STDERR,(const unsigned char *)"ipcping: IPC error\n");
    return code?code:1;
}
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    const unsigned char *name=(const unsigned char *)"echo",*text;
    udeks_ipc_handle sender,found;
    unsigned char count=0,i,stop,rc=0;
    unsigned int attempts;
    if(argc==2)text=argv[1];
    else if(argc==3) { name=argv[1];text=argv[2]; }
    else { udeks_write(UDEKS_STDERR,(const unsigned char *)"ipcping [endpoint] text|--stop\n");return 2; }
    stop=!strcmp((const char *)text,"--stop");
    if(!stop) {
        while(count<15 && text[count])++count;
        if(!count || text[count]) { udeks_write(UDEKS_STDERR,(const unsigned char *)"ipcping: use 1-15 bytes\n");return 2; }
    }
    ipc_client_peer=udeks_ipc_lookup(name);
    if(!ipc_client_peer)return error(udeks_errno);
    ipc_client_handle=udeks_ipc_create((const unsigned char *)"reply");
    if(!ipc_client_handle)return error(udeks_errno);
    ipc_client_reply[0]=stop?IPC_DEMO_STOP:IPC_DEMO_DATA;
    for(i=0;i<count;++i)ipc_client_reply[1+i]=text[i];
    for(attempts=0;attempts<IPC_DEMO_WAIT;++attempts) {
        if(!udeks_ipc_send(ipc_client_peer,ipc_client_handle,ipc_client_reply,count+1))break;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1)) { rc=udeks_errno;goto cleanup; }
    }
    if(attempts==IPC_DEMO_WAIT) { rc=UDEKS_TREQ_EAGAIN;goto cleanup; }
    ipc_client_state=1;
    for(attempts=0;attempts<IPC_DEMO_WAIT;++attempts) {
        ipc_client_count=udeks_ipc_receive(ipc_client_handle,&sender,ipc_client_reply,sizeof(ipc_client_reply));
        if(ipc_client_count!=UDEKS_IO_ERROR)break;
        if(udeks_errno!=UDEKS_TREQ_EAGAIN || udeks_sleep(1)) { rc=udeks_errno;goto cleanup; }
    }
    if(attempts==IPC_DEMO_WAIT) { rc=UDEKS_TREQ_EAGAIN;goto cleanup; }
    if(sender!=ipc_client_peer || ipc_client_count!=count+1 ||
       ipc_client_reply[0]!=(stop?IPC_DEMO_STOPPED:IPC_DEMO_REPLY)) { rc=UDEKS_TREQ_EPROTO;goto cleanup; }
    if(!stop) {
        /* The client independently checks exact content, not just readiness. */
        for(i=0;i<count;++i) {
            unsigned char expected=text[i];
            if(expected>='a' && expected<='z')expected-='a'-'A';
            if(ipc_client_reply[1+i]!=expected) { rc=UDEKS_TREQ_EPROTO;goto cleanup; }
        }
        udeks_write(UDEKS_STDOUT,(const unsigned char *)"reply: ");
        if(udeks_write_bytes(UDEKS_STDOUT,ipc_client_reply+1,count)!=count) { rc=udeks_errno;goto cleanup; }
        udeks_write_byte(UDEKS_STDOUT,'\n');
    } else {
        /* Sender retirement purges queued messages. Keep this endpoint live
         * until the server consumes ACK and closes its endpoint. */
        ipc_client_reply[0]=IPC_DEMO_ACK;
        if(udeks_ipc_send(ipc_client_peer,ipc_client_handle,ipc_client_reply,1)) { rc=udeks_errno;goto cleanup; }
        for(attempts=0;attempts<IPC_DEMO_WAIT;++attempts) {
            found=udeks_ipc_lookup(name);
            if((!found && udeks_errno==UDEKS_TREQ_ENOENT) || (found && found!=ipc_client_peer))break;
            if(!found || udeks_sleep(1)) { rc=udeks_errno;goto cleanup; }
        }
        if(attempts==IPC_DEMO_WAIT) { rc=UDEKS_TREQ_EAGAIN;goto cleanup; }
        udeks_write(UDEKS_STDOUT,(const unsigned char *)"ipcping: server stopped\n");
    }
    ipc_client_state=2;
cleanup:
    if(udeks_ipc_close(ipc_client_handle) && !rc)rc=udeks_errno;
    return rc?error(rc):0;
}

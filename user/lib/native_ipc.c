/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/native_ipc.h"
#include "udeks/task_request.h"
#ifdef UDEKS_NATIVE_IPC_HOST_TEST
extern volatile unsigned char ipc_test_record[38];
#define R ipc_test_record
#else
extern volatile unsigned char udeks_native_console_record[38];
#define R udeks_native_console_record
#endif
#define P (R+14)
extern void udeks_native_console_gate(void);
static unsigned char sequence;
static unsigned char fail(unsigned char error)
{ udeks_errno=error;return UDEKS_IO_ERROR; }
/* IPC changes COUNT on success; the ordinary stream helper preserves COUNT.
 * Validate the whole envelope before interpreting a handle or copying data. */
static unsigned char request(unsigned char action,unsigned char count)
{
    unsigned char seq=++sequence;
    R[0]='U';R[1]='T';R[2]='R';R[3]='Q';R[4]=0;R[5]=21;
    R[7]=29;R[8]=seq;R[9]=action;R[10]=count;R[11]=0;R[12]=0;R[13]=0;
    R[6]=1;udeks_native_console_gate();
    if(R[0]!='U' || R[1]!='T' || R[2]!='R' || R[3]!='Q' || R[4] ||
       R[5]!=21 || R[7]!=29 || R[8]!=seq || R[9]!=action || R[13])
        return fail(UDEKS_TREQ_EPROTO);
    if(R[6]==128) {
        if(!R[12] || R[11] || R[10]!=count) return fail(UDEKS_TREQ_EPROTO);
        return fail(R[12]);
    }
    if(R[6]!=2 || R[12] || R[10]>24 || R[11]!=R[10])return fail(UDEKS_TREQ_EPROTO);
    udeks_errno=0;return R[10];
}
static void put(unsigned char offset,udeks_ipc_handle handle)
{ P[offset]=(unsigned char)handle;P[offset+1]=(unsigned char)(handle>>8); }
static udeks_ipc_handle get(void)
{ return P[0]|((udeks_ipc_handle)P[1]<<8); }
static udeks_ipc_handle named(unsigned char action,const unsigned char *name)
{
    unsigned char n=0,result;
    if(!name) { fail(UDEKS_TREQ_EINVAL);return 0; }
    while(n<UDEKS_IPC_NAME_MAX && name[n]) {
        if(name[n]<33 || name[n]>126) { fail(UDEKS_TREQ_EINVAL);return 0; }
        P[n]=name[n];++n;
    }
    if(!n || name[n]) { fail(UDEKS_TREQ_EINVAL);return 0; }
    result=request(action,n);
    if(result==UDEKS_IO_ERROR)return 0;
    if(result!=2 || !get()) { fail(UDEKS_TREQ_EPROTO);return 0; }
    return get();
}
udeks_ipc_handle udeks_ipc_create(const unsigned char *name)
{ return named(UDEKS_IPC_CREATE,name); }
udeks_ipc_handle udeks_ipc_lookup(const unsigned char *name)
{ return named(UDEKS_IPC_LOOKUP,name); }
unsigned char udeks_ipc_send(udeks_ipc_handle destination,udeks_ipc_handle source,
                            const unsigned char *buffer,unsigned char count)
{
    unsigned char i,result;
    if(!destination || !source)return fail(UDEKS_TREQ_EBADF);
    if(!buffer || !count || count>UDEKS_IPC_MESSAGE_MAX)return fail(UDEKS_TREQ_EINVAL);
    put(0,destination);put(2,source);
    for(i=0;i<count;++i)P[4+i]=buffer[i];
    result=request(UDEKS_IPC_SEND,count+4);
    if(result==UDEKS_IO_ERROR)return result;
    return result?fail(UDEKS_TREQ_EPROTO):0;
}
unsigned char udeks_ipc_receive(udeks_ipc_handle endpoint,udeks_ipc_handle *sender,
                               unsigned char *buffer,unsigned char capacity)
{
    unsigned char i,result;
    udeks_ipc_handle origin;
    if(!endpoint)return fail(UDEKS_TREQ_EBADF);
    if(!sender || capacity>UDEKS_IPC_MESSAGE_MAX || (!buffer && capacity))return fail(UDEKS_TREQ_EINVAL);
    put(0,endpoint);P[2]=capacity;
    result=request(UDEKS_IPC_RECEIVE,3);
    if(result==UDEKS_IO_ERROR)return result;
    if(result<3 || result>capacity+2 || !get())return fail(UDEKS_TREQ_EPROTO);
    origin=get();result-=2;
    for(i=0;i<result;++i)buffer[i]=P[2+i];
    *sender=origin;return result;
}
unsigned char udeks_ipc_close(udeks_ipc_handle endpoint)
{
    unsigned char result;
    if(!endpoint)return fail(UDEKS_TREQ_EBADF);
    put(0,endpoint);result=request(UDEKS_IPC_CLOSE,2);
    if(result==UDEKS_IO_ERROR)return result;
    return result?fail(UDEKS_TREQ_EPROTO):0;
}

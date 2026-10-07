/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Transient console SDK. No kernel imports, policy or automatic write retry. */
#include "udeks/program.h"
#include "udeks/task_request.h"
#ifdef UDEKS_FS_CLIENT_TEST
extern unsigned char udeks_file_payload[24];
#define PAYLOAD udeks_file_payload
#else
#define PAYLOAD ((volatile unsigned char *)0xf367)
#endif
unsigned char udeks_errno;
unsigned char __fastcall__ udeks_fs_request(unsigned char op, unsigned char fd, unsigned char count);

static unsigned char invalid(void)
{
    udeks_errno=UDEKS_TREQ_EINVAL;
    return UDEKS_IO_ERROR;
}
unsigned char udeks_fs_path_request(unsigned char op, unsigned char mode, const unsigned char *path)
{
    unsigned char n=0;
    if(!path) return invalid();
    while(path[n]) {
        if(n==23) return invalid();
        PAYLOAD[n]=path[n]; ++n;
    }
    if(!n) return invalid();
    PAYLOAD[n]=0;
    return udeks_fs_request(op,mode,n);
}
unsigned char udeks_open(const unsigned char *path, unsigned char mode)
{
    return udeks_fs_path_request(UDEKS_TREQ_OP_OPEN,mode,path);
}
unsigned char udeks_fs_receive(unsigned char op, unsigned char fd, unsigned char *buffer, unsigned char count)
{
    unsigned char n,i;
    if(count>24 || (count && !buffer)) return invalid();
    n=udeks_fs_request(op,fd,count);
    if(n==UDEKS_IO_ERROR) return n;
    if(n>count) { udeks_errno=UDEKS_TREQ_EIO; return UDEKS_IO_ERROR; }
    for(i=0;i<n;++i) buffer[i]=PAYLOAD[i];
    return n;
}
unsigned char udeks_read(unsigned char fd, unsigned char *buffer, unsigned char count)
{
    return udeks_fs_receive(UDEKS_TREQ_OP_READ,fd,buffer,count);
}
unsigned char udeks_write_bytes(unsigned char fd, const unsigned char *buffer, unsigned char count)
{
    unsigned char i,n;
    if(count>24 || (count && !buffer)) return invalid();
    for(i=0;i<count;++i) PAYLOAD[i]=buffer[i];
    n=udeks_fs_request(UDEKS_TREQ_OP_WRITE,fd,count);
    if(n!=UDEKS_IO_ERROR && n>count) { udeks_errno=UDEKS_TREQ_EIO; return UDEKS_IO_ERROR; }
    return n;
}
unsigned char udeks_close(unsigned char fd)
{
    return udeks_fs_request(UDEKS_TREQ_OP_CLOSE,fd,0);
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Optional archive member: file-only clients do not pay for metadata calls. */
#include "udeks/program.h"
#include "udeks/task_request.h"
#ifdef UDEKS_FS_CLIENT_TEST
extern unsigned char udeks_file_payload[24];
#define PAYLOAD udeks_file_payload
#else
#define PAYLOAD ((volatile unsigned char *)0xf367)
#endif
unsigned char udeks_fs_path_request(unsigned char op,unsigned char mode,const unsigned char *path);
unsigned char udeks_fs_receive(unsigned char op,unsigned char fd,unsigned char *buffer,unsigned char count);
unsigned char udeks_getdents(unsigned char fd,unsigned char *buffer,unsigned char count)
{
    return udeks_fs_receive(UDEKS_TREQ_OP_GETDENTS,fd,buffer,count);
}
unsigned char udeks_stat(const unsigned char *path,unsigned char *status)
{
    unsigned char n,i;
    if(!status) { udeks_errno=UDEKS_TREQ_EINVAL; return UDEKS_IO_ERROR; }
    n=udeks_fs_path_request(UDEKS_TREQ_OP_STAT,0,path);
    if(n==UDEKS_IO_ERROR) return n;
    if(n!=3) { udeks_errno=UDEKS_TREQ_EIO; return UDEKS_IO_ERROR; }
    for(i=0;i<3;++i) status[i]=PAYLOAD[i];
    return n;
}

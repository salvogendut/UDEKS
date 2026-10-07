/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Public console SDK: intentionally return without closing a written stream. */
#include "udeks/program.h"
static unsigned char data[24];
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned char fd,i;
    if(argc!=2) return 90;
    fd=udeks_open(argv[1],UDEKS_O_CREATE_EXCL);
    if(fd==UDEKS_IO_ERROR) return udeks_errno;
    for(i=0;i<24;++i) data[i]=i;
    return udeks_write_bytes(fd,data,24)==24 ? 0 : 91;
}

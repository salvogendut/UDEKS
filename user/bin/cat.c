/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent cooperative file reader: no app catalogue or kernel imports. */
#include "udeks/native_console.h"
#include "udeks/task_request.h"

static unsigned char fail(unsigned char error)
{
    const unsigned char *message;
    message=(const unsigned char *)(error==UDEKS_TREQ_ENOENT ? "No such file or directory" :
        error==UDEKS_TREQ_EISDIR ? "Is a directory" :
        error==UDEKS_TREQ_EMFILE || error==UDEKS_TREQ_EBUSY ? "Filesystem busy" :
        error==UDEKS_TREQ_ENODEV ? "No such device" : "I/O error");
    udeks_write(2,(const unsigned char *)"cat: ");
    udeks_write(2,message); udeks_write_byte(2,'\n');
    return 1;
}

unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char fd,n,error,buffer[24];
    if(argc!=2) {
        udeks_write(2,(const unsigned char *)"cat FILE\n");
        return 2;
    }
    fd=udeks_open(argv[1],UDEKS_O_RDONLY);
    if(fd==UDEKS_IO_ERROR) return fail(udeks_errno);
    error=0;
    while((n=udeks_read(fd,buffer,sizeof(buffer)))!=0) {
        if(n==UDEKS_IO_ERROR) { error=udeks_errno; break; }
        if(udeks_write_bytes(1,buffer,n)!=n) { error=udeks_errno?udeks_errno:UDEKS_TREQ_EIO; break; }
        /* No IEC/MMU lease crosses this point; only our file handle and
         * private buffer survive. Input, time and graphical peers can run. */
        if(udeks_sleep(1)==UDEKS_IO_ERROR) { error=udeks_errno; break; }
    }
    if(udeks_close(fd)==UDEKS_IO_ERROR && !error) error=udeks_errno;
    return error ? fail(error) : 0;
}

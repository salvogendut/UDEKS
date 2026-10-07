/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent create/readback fixture: repeating bytes 0..255, no retries. */
#include <string.h>
#include "udeks/program.h"
static unsigned char buffer[24];

static unsigned char fail(unsigned char error)
{
    udeks_write(2,(const unsigned char *)"save: ");
    udeks_write(2,udeks_error_string(error));
    udeks_write_byte(2,'\n');
    return 1;
}
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    const unsigned char *path,*p;
    unsigned int size=515,position,value;
    unsigned char check=0,arg=1,fd,n,i,count,error,closed;
    if(argc>1 && !strcmp((const char *)argv[1],"-c")) { check=1; arg=2; }
    if(argc<arg+1u || argc>arg+2u) goto usage;
    path=argv[arg];
    if(argc==arg+2u) {
        p=argv[arg+1]; value=0;
        if(!*p) goto usage;
        while(*p) {
            if(*p<'0'||*p>'9'||value>409) goto usage;
            value=value*10+*p++-'0';
            if(value>4096) goto usage;
        }
        size=value;
    }
    if(!check) {
        fd=udeks_open(path,UDEKS_O_CREATE_EXCL);
        if(fd==UDEKS_IO_ERROR) return fail(udeks_errno);
        error=0; position=0;
        while(position<size) {
            count=size-position<24 ? size-position : 24;
            for(i=0;i<count;++i) buffer[i]=(unsigned char)(position+i);
            n=udeks_write_bytes(fd,buffer,count);
            if(n!=count) { error=udeks_errno ? udeks_errno : 5; break; }
            position+=count;
        }
        closed=udeks_close(fd);
        if(!error && closed==UDEKS_IO_ERROR) error=udeks_errno;
        if(error) return fail(error); /* no rollback: partial file may remain */
    }
    fd=udeks_open(path,UDEKS_O_RDONLY);
    if(fd==UDEKS_IO_ERROR) return fail(udeks_errno);
    position=0; error=0;
    for(;;) {
        n=udeks_read(fd,buffer,24);
        if(n==UDEKS_IO_ERROR) { error=udeks_errno; break; }
        if(!n) break;
        if(position+n>size) { error=5; break; }
        for(i=0;i<n;++i) if(buffer[i]!=(unsigned char)(position+i)) error=5;
        if(error) break;
        position+=n;
    }
    if(!error && position!=size) error=5;
    closed=udeks_close(fd);
    if(!error && closed==UDEKS_IO_ERROR) error=udeks_errno;
    if(error) return fail(error);
    udeks_write(1,(const unsigned char *)(check ? "save: verified\n" : "save: created and verified\n"));
    return 0;
usage:
    udeks_write(2,(const unsigned char *)"save [-c] FILE [0..4096 bytes; default 515]\n");
    return 1;
}

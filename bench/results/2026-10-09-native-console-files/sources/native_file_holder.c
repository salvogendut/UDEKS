/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Test-only release flag; all file/exit operations use the public SDK. */
#include "udeks/native_console.h"
unsigned char file_stage, file_error;
volatile unsigned char file_release;
unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char fd,n,buffer[5];
    unsigned char writer=argc==2 && argv[1][0]=='w';
    static const unsigned char data[]={0,255,128,'N','a','t','i','v','e','\n'};
    fd=udeks_open((const unsigned char *)(writer?"/native-data":"/hello"),
                  writer?UDEKS_O_CREATE_EXCL:UDEKS_O_RDONLY);
    if(fd==255) goto failed;
    if(writer && udeks_write_bytes(fd,data,sizeof(data))!=sizeof(data)) goto failed;
    file_stage=2;
    while(!file_release) if(udeks_sleep(1)) goto failed;
    if(!writer) {
        n=udeks_read(fd,buffer,5);
        if(n!=5 || buffer[0]!='H' || buffer[1]!='E' || buffer[2]!='L' ||
           buffer[3]!='L' || buffer[4]!='O') goto failed;
    }
    file_stage=3;
    /* Deliberately leak: EXIT must close before the allocation is reused. */
    return 17;
failed:
    file_error=udeks_errno?udeks_errno:5; file_stage=128; return 1;
}

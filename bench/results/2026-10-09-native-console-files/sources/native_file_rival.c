/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/native_console.h"
unsigned char rival_stage, rival_error;
volatile unsigned char rival_release;
unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char c=165;
    (void)argc; (void)argv;
    rival_stage=1;
    while(!rival_release) if(udeks_sleep(1)) goto failed;
    if(udeks_read(4,&c,1)!=255 || udeks_errno!=9 || c!=165 ||
       udeks_write_bytes(4,&c,1)!=255 || udeks_errno!=9 ||
       udeks_close(4)!=255 || udeks_errno!=9 ||
       udeks_open((const unsigned char *)"/hello",UDEKS_O_RDONLY)!=255 ||
       udeks_errno!=24) goto failed;
    rival_stage=2; return 0;
failed:
    rival_error=udeks_errno?udeks_errno:5; rival_stage=128; return 1;
}

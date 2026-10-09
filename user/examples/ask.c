/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent console example: Enter submits; Ctrl+C cancels via parent ush. */
#include "udeks/native_console.h"

unsigned char ask_stage;
unsigned char ask_error;

unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char text[24],n;
    (void)argc; (void)argv;
    ask_stage=1;
    if(udeks_write(1,(const unsigned char *)"Type a line (Enter), or Ctrl+C:\n")) return 1;
    do {
        n=udeks_read(0,text,sizeof(text));
        if(n==UDEKS_IO_ERROR) { ask_error=udeks_errno; return 1; }
        ask_stage=2;
        if(udeks_write_bytes(1,text,n)!=n) return 1;
    } while(!n || text[n-1]!='\n');
    ask_stage=3;
    return 0;
}

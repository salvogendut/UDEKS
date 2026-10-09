/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/native_console.h"
#include "udeks/task_request.h"
extern unsigned char udeks_native_request(unsigned char, unsigned char, unsigned char);
unsigned char input_checks, input_failure;
unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char c=0xa5;
    (void)argc; (void)argv;
    for(;;) {
        if(udeks_poll(0,0)!=255 || udeks_errno!=5 ||
           udeks_poll(0,65535)!=255 || udeks_errno!=5 ||
           udeks_read(0,&c,1)!=255 || udeks_errno!=5 || c!=0xa5 ||
           udeks_native_request(1,0,1)!=255 || udeks_errno!=5) {
            input_failure=1; return 1;
        }
        ++input_checks;
        if(udeks_sleep(60)) { input_failure=2; return 2; }
    }
}

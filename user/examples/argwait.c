/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Silent qualification peer: exercises private arguments without background
 * output or stdin, whose terminal policy is a later increment. */
#include "udeks/native_console.h"
#include <string.h>
unsigned char quiet_stage,quiet_failure,quiet_arguments[81];
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned char i;
    if(argc!=1 || !argv || argv[1] || strcmp((const char *)argv[0],"quiet")) return 99;
    memcpy(quiet_arguments,(const void *)0x80,sizeof(quiet_arguments));
    quiet_stage=1;
    for(i=0;i<3;++i) {
        if(udeks_sleep(600) || memcmp(quiet_arguments,(const void *)0x80,sizeof(quiet_arguments))) {
            quiet_failure=1; return 98;
        }
    }
    quiet_stage=2;
    return 67;
}

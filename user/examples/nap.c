/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Silent cancellation fixture: no window, input or background output. It
 * never exits normally, so a returned prompt cannot be a natural completion. */
#include "udeks/native_console.h"
unsigned int nap_steps;
unsigned char nap_failure;
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    if(!argc || !argv || argv[argc]) return 99;
    for(;;) {
        ++nap_steps;
        if(udeks_sleep(600)) { nap_failure=1; return 98; }
    }
}

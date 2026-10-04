/* SPDX-License-Identifier: GPL-3.0-or-later */
/* An ordinary disk command: no OS registration or private kernel symbols. */
#include "udeks/program.h"

static unsigned char ran;

unsigned char udeks_program_main(unsigned char count, unsigned char **arguments)
{
    unsigned char i;
    if (ran) return 99;              /* loader must clear BSS on every run */
    ran = 1;
    udeks_write(UDEKS_STDOUT, (const unsigned char *)"args: fresh BSS\n");
    for (i = 0; i < count; ++i) {
        udeks_write(UDEKS_STDOUT, (const unsigned char *)"[");
        udeks_write(UDEKS_STDOUT, arguments[i]);
        udeks_write(UDEKS_STDOUT, (const unsigned char *)"]\n");
    }
    udeks_write(UDEKS_STDERR, (const unsigned char *)"args: stderr works\n");
    return 37;                      /* qualification checks the loader status */
}

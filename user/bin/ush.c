/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/program.h"

static unsigned char started;

unsigned char udeks_ush_poll(void)
{
    if (started == 0) {
        started = 1;
        udeks_write(
            UDEKS_STDOUT,
            (const unsigned char *)"ush: bank-1 task ready\n");
    }
    return UDEKS_EXIT_SUCCESS;
}

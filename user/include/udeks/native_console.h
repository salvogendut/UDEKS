/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_NATIVE_CONSOLE_H
#define UDEKS_NATIVE_CONSOLE_H

#include "udeks/program.h"

/* Experimental cooperative console runtime, using existing UTRQ operations.
 * WRITE accepts descriptors 1/2 only and copies at most 24 bytes per request.
 * SLEEP accepts 1..600 logical 1/60-second ticks; returns 0 or IO_ERROR.
 * No stdin, background terminal policy, filesystem or raw bank-0 veneers.
 * This first execution probe receives argc=0, argv=NULL; argument delivery
 * and foreground exit-status reporting still need the launch contract. */
unsigned char udeks_sleep(unsigned int ticks);

#endif

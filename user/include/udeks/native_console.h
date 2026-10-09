/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_NATIVE_CONSOLE_H
#define UDEKS_NATIVE_CONSOLE_H

#include "udeks/program.h"

/* Experimental cooperative console runtime, using existing UTRQ operations.
 * WRITE accepts descriptors 1/2 only and copies at most 24 bytes per request.
 * SLEEP accepts 1..600 logical 1/60-second ticks; returns 0 or IO_ERROR.
 * No stdin, background terminal policy, filesystem or raw bank-0 veneers.
 * Entry receives bounded task-private argc/argv via UARG 0.1 (see executable
 * ABI): at most 8 arguments, within the shell's 54-character input line.
 * Ordinary foreground return becomes the shell's eight-bit exit status.
 * This runtime requires an argument-enabled kernel; old kernels return 126. */
unsigned char udeks_sleep(unsigned int ticks);

#endif

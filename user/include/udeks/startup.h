/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_STARTUP_H
#define UDEKS_STARTUP_H
#define UDEKS_STARTUP_MAX 255u
#define UDEKS_STARTUP_LINE 54u
/* Read, close and validate before exposing any commands; root stays mounted.
 * 0 = absent/empty; 1 = ready; 255 = failure (no commands may run). */
unsigned char udeks_startup_begin(unsigned char device);
/* Copy the next nonempty line into a 55-byte buffer, or return 0 at EOF. */
unsigned char udeks_startup_next(unsigned char *line);
#endif

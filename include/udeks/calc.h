/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_CALC_H
#define UDEKS_CALC_H

/* Application model, not a kernel service. Values are signed hundredths. */
#define UDEKS_CALC_MAX 20000000L
#define UDEKS_CALC_OK 0u
#define UDEKS_CALC_DIV_ZERO 1u
#define UDEKS_CALC_OVERFLOW 2u

extern long udeks_calc_value;
extern unsigned char udeks_calc_error;
void udeks_calc_reset(void);
void udeks_calc_key(unsigned char key);
/* Buffer must hold 12 bytes. Always includes two fractional digits. */
void udeks_calc_format(char *buffer);
#endif

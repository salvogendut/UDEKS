/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_MOUSE1351_H
#define UDEKS_MOUSE1351_H

#define UDEKS_MOUSE1351_LEFT_BUTTON     0x10u
#define UDEKS_MOUSE1351_RIGHT_BUTTON    0x01u

void udeks_mouse1351_initialize(unsigned char pot_x, unsigned char pot_y);
void udeks_mouse1351_decode(
    unsigned char pot_x, unsigned char pot_y, unsigned char active,
    signed char *dx, signed char *dy, unsigned char *buttons);

#endif

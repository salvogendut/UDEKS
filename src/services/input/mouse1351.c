/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/mouse1351.h"

static unsigned char old_pot_x;
static unsigned char old_pot_y;

static signed char decode_axis(unsigned char current, unsigned char *previous)
{
    unsigned char delta;
    unsigned char magnitude;

    delta = (unsigned char)((current - *previous) & 0x7Fu);
    if (delta < 0x40u) {
        magnitude = (unsigned char)(delta >> 1);
        if (magnitude == 0) {
            return 0;
        }
        *previous = current;
        return (signed char)magnitude;
    }
    magnitude = (unsigned char)((0x80u - delta) >> 1);
    if (magnitude == 0) {
        return 0;
    }
    *previous = current;
    return (signed char)(-(signed char)magnitude);
}

void udeks_mouse1351_initialize(unsigned char pot_x, unsigned char pot_y)
{
    old_pot_x = pot_x;
    old_pot_y = pot_y;
}

void udeks_mouse1351_decode(
    unsigned char pot_x, unsigned char pot_y, unsigned char active,
    signed char *dx, signed char *dy, unsigned char *buttons)
{
    *dx = decode_axis(pot_x, &old_pot_x);
    *dy = (signed char)-decode_axis(pot_y, &old_pot_y);
    *buttons = 0;
    if ((active & UDEKS_MOUSE1351_LEFT_BUTTON) != 0) {
        *buttons |= 1u;
    }
    if ((active & UDEKS_MOUSE1351_RIGHT_BUTTON) != 0) {
        *buttons |= 2u;
    }
}

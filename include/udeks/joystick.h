/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_JOYSTICK_H
#define UDEKS_JOYSTICK_H

#define UDEKS_JOYSTICK_UP       0x01u
#define UDEKS_JOYSTICK_DOWN     0x02u
#define UDEKS_JOYSTICK_LEFT     0x04u
#define UDEKS_JOYSTICK_RIGHT    0x08u
#define UDEKS_JOYSTICK_FIRE     0x10u

#define UDEKS_JOYSTICK_STEP     3

void udeks_joystick_initialize(unsigned char active);
void udeks_joystick_decode(
    unsigned char active, signed char *dx, signed char *dy,
    unsigned char *buttons);

#endif

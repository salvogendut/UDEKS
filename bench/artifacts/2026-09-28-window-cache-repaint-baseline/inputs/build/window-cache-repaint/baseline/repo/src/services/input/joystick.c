/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/joystick.h"

static unsigned char candidate_state;

void udeks_joystick_initialize(unsigned char active)
{
    candidate_state = active;
}

void udeks_joystick_decode(
    unsigned char active, signed char *dx, signed char *dy,
    unsigned char *buttons)
{
    *dx = 0;
    *dy = 0;
    *buttons = 0;
    if (active != candidate_state) {
        candidate_state = active;
        return;
    }
    if ((active & UDEKS_JOYSTICK_LEFT) != 0 &&
        (active & UDEKS_JOYSTICK_RIGHT) == 0) {
        *dx = -UDEKS_JOYSTICK_STEP;
    } else if ((active & UDEKS_JOYSTICK_RIGHT) != 0 &&
               (active & UDEKS_JOYSTICK_LEFT) == 0) {
        *dx = UDEKS_JOYSTICK_STEP;
    }
    if ((active & UDEKS_JOYSTICK_UP) != 0 &&
        (active & UDEKS_JOYSTICK_DOWN) == 0) {
        *dy = -UDEKS_JOYSTICK_STEP;
    } else if ((active & UDEKS_JOYSTICK_DOWN) != 0 &&
               (active & UDEKS_JOYSTICK_UP) == 0) {
        *dy = UDEKS_JOYSTICK_STEP;
    }
    *buttons = (active & UDEKS_JOYSTICK_FIRE) != 0 ? 1u : 0u;
}

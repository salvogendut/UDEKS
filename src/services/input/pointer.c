/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/joystick.h"
#include "udeks/mouse1351.h"
#include "udeks/pointer.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_POINTER_STATUS_BASE + (offset)))
#define VIC_RASTER (*(volatile unsigned char *)0xD012u)

extern unsigned char udeks_control_joystick2;
extern unsigned char udeks_control_mouse1_buttons;
extern unsigned char udeks_control_mouse1_x;
extern unsigned char udeks_control_mouse1_y;
extern void udeks_control_ports_start(void);
extern void udeks_control_ports_sample(void);
extern unsigned char udeks_control_ports_active(void);

static unsigned int pointer_x_position;
static unsigned char pointer_y_position;
static unsigned char pointer_button_state;
static unsigned char frame_latched;
static unsigned char mouse_settling;
static unsigned char settle_raster;
static unsigned char warmup_samples;

static void increment_counter(unsigned char low_offset)
{
    ++STATUS_BYTE(low_offset);
    if (STATUS_BYTE(low_offset) == 0) {
        ++STATUS_BYTE(low_offset + 1u);
    }
}

static unsigned int apply_x_delta(unsigned int position, signed char delta)
{
    unsigned char amount;

    if (delta < 0) {
        amount = (unsigned char)-delta;
        if (position < UDEKS_POINTER_X_MIN + amount) {
            return UDEKS_POINTER_X_MIN;
        }
        return (unsigned int)(position - amount);
    }
    amount = (unsigned char)delta;
    if (position > UDEKS_POINTER_X_MAX - amount) {
        return UDEKS_POINTER_X_MAX;
    }
    return (unsigned int)(position + amount);
}

static unsigned char apply_y_delta(
    unsigned char position, signed char delta)
{
    unsigned char amount;

    if (delta < 0) {
        amount = (unsigned char)-delta;
        if (position < UDEKS_POINTER_Y_MIN + amount) {
            return UDEKS_POINTER_Y_MIN;
        }
        return (unsigned char)(position - amount);
    }
    amount = (unsigned char)delta;
    if (position > UDEKS_POINTER_Y_MAX - amount) {
        return UDEKS_POINTER_Y_MAX;
    }
    return (unsigned char)(position + amount);
}

static void publish_position(void)
{
    STATUS_BYTE(8) = (unsigned char)pointer_x_position;
    STATUS_BYTE(9) = (unsigned char)(pointer_x_position >> 8);
    STATUS_BYTE(10) = pointer_y_position;
    STATUS_BYTE(11) = pointer_button_state;
}

unsigned char udeks_pointer_start(void)
{
    unsigned char offset;

    for (offset = 0; offset < UDEKS_POINTER_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'P';
    STATUS_BYTE(1) = 'T';
    STATUS_BYTE(2) = 'R';
    STATUS_BYTE(3) = 'I';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_POINTER_STARTING;
    STATUS_BYTE(7) = UDEKS_POINTER_FLAG_MOUSE1 |
        UDEKS_POINTER_FLAG_JOYSTICK2 | UDEKS_POINTER_FLAG_1351 |
        UDEKS_POINTER_FLAG_FRAME_POLL;
    pointer_x_position = UDEKS_POINTER_X_INITIAL;
    pointer_y_position = UDEKS_POINTER_Y_INITIAL;
    pointer_button_state = 0;
    frame_latched = 0;
    mouse_settling = 0;
    settle_raster = 0;
    warmup_samples = 2;
    udeks_control_ports_start();
    udeks_control_ports_sample();
    udeks_mouse1351_initialize(
        udeks_control_mouse1_x, udeks_control_mouse1_y);
    udeks_joystick_initialize(udeks_control_joystick2);
    publish_position();
    STATUS_BYTE(12) = udeks_control_joystick2;
    STATUS_BYTE(13) = udeks_control_mouse1_buttons;
    STATUS_BYTE(14) = udeks_control_mouse1_x;
    STATUS_BYTE(15) = udeks_control_mouse1_y;
    STATUS_BYTE(5) = UDEKS_POINTER_READY;
    return UDEKS_POINTER_OK;
}

unsigned char udeks_pointer_poll(void)
{
    signed char mouse_dx;
    signed char mouse_dy;
    signed char joystick_dx;
    signed char joystick_dy;
    signed char dx;
    signed char dy;
    unsigned char mouse_buttons;
    unsigned char joystick_buttons;
    unsigned char sources;

    if (VIC_RASTER < 180u && mouse_settling == 0) {
        frame_latched = 0;
        STATUS_BYTE(26) = 0;
    }
    if (frame_latched != 0) {
        return UDEKS_POINTER_OK;
    }
    if (mouse_settling == 0) {
        if (VIC_RASTER < 200u) {
            return UDEKS_POINTER_OK;
        }
        mouse_settling = 1;
        settle_raster = VIC_RASTER;
        STATUS_BYTE(26) = 1;
        return UDEKS_POINTER_OK;
    }
    if ((unsigned char)(VIC_RASTER - settle_raster) < 26u) {
        return UDEKS_POINTER_OK;
    }
    udeks_control_ports_sample();
    if (warmup_samples != 0) {
        udeks_mouse1351_initialize(
            udeks_control_mouse1_x, udeks_control_mouse1_y);
        udeks_joystick_initialize(udeks_control_joystick2);
        --warmup_samples;
        mouse_dx = 0;
        mouse_dy = 0;
        mouse_buttons = 0;
        joystick_dx = 0;
        joystick_dy = 0;
        joystick_buttons = 0;
    } else {
        udeks_mouse1351_decode(
            udeks_control_mouse1_x, udeks_control_mouse1_y,
            udeks_control_mouse1_buttons, &mouse_dx, &mouse_dy,
            &mouse_buttons);
        udeks_joystick_decode(
            udeks_control_joystick2, &joystick_dx, &joystick_dy,
            &joystick_buttons);
    }
    dx = (signed char)(mouse_dx + joystick_dx);
    dy = (signed char)(mouse_dy + joystick_dy);
    sources = 0;
    if (mouse_dx != 0 || mouse_dy != 0 || mouse_buttons != 0) {
        sources |= UDEKS_POINTER_SOURCE_MOUSE;
    }
    if (joystick_dx != 0 || joystick_dy != 0 || joystick_buttons != 0) {
        sources |= UDEKS_POINTER_SOURCE_JOYSTICK;
    }
    if (dx != 0 || dy != 0) {
        pointer_x_position = apply_x_delta(pointer_x_position, dx);
        pointer_y_position = apply_y_delta(pointer_y_position, dy);
        increment_counter(20u);
    }
    if ((sources & UDEKS_POINTER_SOURCE_MOUSE) != 0) {
        increment_counter(22u);
    }
    if ((sources & UDEKS_POINTER_SOURCE_JOYSTICK) != 0) {
        increment_counter(24u);
    }
    pointer_button_state = (unsigned char)(
        mouse_buttons | (unsigned char)(joystick_buttons << 2));
    STATUS_BYTE(12) = udeks_control_joystick2;
    STATUS_BYTE(13) = udeks_control_mouse1_buttons;
    STATUS_BYTE(14) = udeks_control_mouse1_x;
    STATUS_BYTE(15) = udeks_control_mouse1_y;
    STATUS_BYTE(16) = (unsigned char)dx;
    STATUS_BYTE(17) = (unsigned char)dy;
    increment_counter(18u);
    mouse_settling = 0;
    frame_latched = 1;
    STATUS_BYTE(26) = 0;
    STATUS_BYTE(27) = sources;
    publish_position();
    return UDEKS_POINTER_OK;
}

unsigned char udeks_pointer_keyboard_allowed(void)
{
    if (mouse_settling != 0 || udeks_control_ports_active() != 0) {
        return 0;
    }
    return 1;
}

unsigned int udeks_pointer_x(void)
{
    return pointer_x_position;
}

unsigned char udeks_pointer_y(void)
{
    return pointer_y_position;
}

unsigned char udeks_pointer_buttons(void)
{
    return pointer_button_state;
}

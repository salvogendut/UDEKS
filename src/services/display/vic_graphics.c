/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/vic_graphics.h"
#include "udeks/pointer.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_VIC_GRAPHICS_STATUS_BASE + (offset)))

extern unsigned char udeks_vic_graphics_enable(void);
extern unsigned char udeks_vic_graphics_disable(void);
extern void udeks_vic_pointer_set_x(unsigned int x);
extern void udeks_vic_pointer_set_y(unsigned char y);

static void increment_counter(unsigned char low_offset)
{
    ++STATUS_BYTE(low_offset);
    if (STATUS_BYTE(low_offset) == 0) {
        ++STATUS_BYTE(low_offset + 1u);
    }
}

static void apply_pointer(unsigned int x, unsigned char y)
{
    udeks_vic_pointer_set_x(x);
    udeks_vic_pointer_set_y(y);
    STATUS_BYTE(10) = (unsigned char)x;
    STATUS_BYTE(11) = (unsigned char)(x >> 8);
    STATUS_BYTE(12) = y;
}

static void update_pointer(void)
{
    unsigned int x;
    unsigned char y;

    x = udeks_pointer_x();
    y = udeks_pointer_y();
    if (STATUS_BYTE(10) != (unsigned char)x ||
        STATUS_BYTE(11) != (unsigned char)(x >> 8)) {
        udeks_vic_pointer_set_x(x);
        STATUS_BYTE(10) = (unsigned char)x;
        STATUS_BYTE(11) = (unsigned char)(x >> 8);
    }
    if (STATUS_BYTE(12) != y) {
        udeks_vic_pointer_set_y(y);
        STATUS_BYTE(12) = y;
    }
}

unsigned char udeks_vic_graphics_start(void)
{
    unsigned char offset;

    for (offset = 0; offset < UDEKS_VIC_GRAPHICS_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'V';
    STATUS_BYTE(1) = 'I';
    STATUS_BYTE(2) = 'C';
    STATUS_BYTE(3) = 'G';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_VIC_GRAPHICS_READY;
    STATUS_BYTE(7) = UDEKS_VIC_GRAPHICS_MODE_HIRES;
    STATUS_BYTE(8) = UDEKS_VIC_COLOR_YELLOW;
    STATUS_BYTE(9) = UDEKS_VIC_COLOR_BLACK;
    STATUS_BYTE(10) = 0xACu;
    STATUS_BYTE(11) = 0u;
    STATUS_BYTE(12) = 0x8Cu;
    STATUS_BYTE(13) = 1u;
    STATUS_BYTE(14) = 0x60u;
    STATUS_BYTE(15) = 0x5Cu;
    STATUS_BYTE(16) = 0xFFu;
    return UDEKS_VIC_GRAPHICS_OK;
}

unsigned char udeks_vic_graphics_poll(void)
{
    if (STATUS_BYTE(5) == UDEKS_VIC_GRAPHICS_ACTIVE) {
        update_pointer();
    }
    return UDEKS_VIC_GRAPHICS_OK;
}

unsigned char udeks_vic_graphics_initialize(void)
{
    unsigned char result;
    unsigned int x;
    unsigned char y;

    if (STATUS_BYTE(5) != UDEKS_VIC_GRAPHICS_READY &&
        STATUS_BYTE(5) != UDEKS_VIC_GRAPHICS_ACTIVE) {
        return UDEKS_VIC_GRAPHICS_NOT_READY;
    }
    result = udeks_vic_graphics_enable();
    if (result != UDEKS_VIC_GRAPHICS_OK) {
        STATUS_BYTE(6) = UDEKS_VIC_GRAPHICS_SETUP_FAILED;
        STATUS_BYTE(5) = UDEKS_VIC_GRAPHICS_ERROR;
        return UDEKS_VIC_GRAPHICS_SETUP_FAILED;
    }
    increment_counter(17u);
    STATUS_BYTE(5) = UDEKS_VIC_GRAPHICS_ACTIVE;
    x = udeks_pointer_x();
    y = udeks_pointer_y();
    apply_pointer(x, y);
    return UDEKS_VIC_GRAPHICS_OK;
}

unsigned char udeks_vic_graphics_shutdown(void)
{
    unsigned char result;

    if (STATUS_BYTE(5) == UDEKS_VIC_GRAPHICS_READY) {
        return UDEKS_VIC_GRAPHICS_OK;
    }
    if (STATUS_BYTE(5) != UDEKS_VIC_GRAPHICS_ACTIVE) {
        return UDEKS_VIC_GRAPHICS_NOT_READY;
    }
    result = udeks_vic_graphics_disable();
    if (result != UDEKS_VIC_GRAPHICS_OK) {
        STATUS_BYTE(6) = UDEKS_VIC_GRAPHICS_SETUP_FAILED;
        STATUS_BYTE(5) = UDEKS_VIC_GRAPHICS_ERROR;
        return UDEKS_VIC_GRAPHICS_SETUP_FAILED;
    }
    increment_counter(19u);
    STATUS_BYTE(5) = UDEKS_VIC_GRAPHICS_READY;
    return UDEKS_VIC_GRAPHICS_OK;
}

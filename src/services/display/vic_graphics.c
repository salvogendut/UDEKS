/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/vic_graphics.h"
#include "udeks/pointer.h"
#include "udeks/xclock.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_VIC_GRAPHICS_STATUS_BASE + (offset)))

extern unsigned char udeks_vic_graphics_enable(void);
extern unsigned char udeks_vic_graphics_disable(void);
extern void udeks_vic_pointer_set_x(unsigned int x);
extern void udeks_vic_pointer_set_y(unsigned char y);
extern void udeks_vic_bitmap_commit_page(unsigned char page);

#pragma bss-name(push, "VICSHADOW")
unsigned char udeks_vic_bitmap_shadow[8192];
#pragma bss-name(pop)

static unsigned char dirty_pages[UDEKS_VIC_BITMAP_PAGES];
static unsigned int bitmap_rows[UDEKS_VIC_HEIGHT];

#define PLOT_UNCHECKED(plot_x, plot_y, plot_color) do { \
    pixel_offset = (unsigned int)(bitmap_rows[(unsigned char)(plot_y)] + \
        ((unsigned int)(plot_x) & 0xFFF8u)); \
    pixel_mask = (unsigned char)(0x80u >> ((unsigned int)(plot_x) & 7u)); \
    if ((plot_color) == UDEKS_VIC_COLOR_BLACK) { \
        udeks_vic_bitmap_shadow[pixel_offset] |= pixel_mask; \
    } else { \
        udeks_vic_bitmap_shadow[pixel_offset] &= \
            (unsigned char)~pixel_mask; \
    } \
    dirty_pages[pixel_offset >> 8] = 1; \
} while (0)

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

static unsigned int bitmap_offset(unsigned int x, unsigned char y)
{
    unsigned int band;

    band = (unsigned int)(y & 0xF8u);
    return (unsigned int)((band << 5) + (band << 3) +
        (x & 0xFFF8u) + (y & 7u));
}

static unsigned int unsigned_magnitude(int value)
{
    return value < 0 ? (unsigned int)-value : (unsigned int)value;
}

void udeks_vic_bitmap_clear(unsigned char color)
{
    unsigned int offset;
    unsigned char page;
    unsigned char value;

    value = color == UDEKS_VIC_COLOR_BLACK ? 0xFFu : 0u;
    for (offset = 0; offset < UDEKS_VIC_BITMAP_SIZE; ++offset) {
        udeks_vic_bitmap_shadow[offset] = value;
    }
    for (page = 0; page < UDEKS_VIC_BITMAP_PAGES; ++page) {
        dirty_pages[page] = 1;
    }
}

void udeks_vic_bitmap_pixel(int x, int y, unsigned char color)
{
    unsigned int pixel_offset;
    unsigned char pixel_mask;

    if (x < 0 || x >= (int)UDEKS_VIC_WIDTH ||
        y < 0 || y >= (int)UDEKS_VIC_HEIGHT) {
        return;
    }
    PLOT_UNCHECKED(x, y, color);
}

void udeks_vic_bitmap_line(
    int x0, int y0, int x1, int y1, unsigned char color)
{
    int dx;
    int dy;
    int error;
    int twice;
    int step_x;
    int step_y;
    unsigned int pixel_offset;
    unsigned char pixel_mask;

    dx = (int)unsigned_magnitude(x1 - x0);
    dy = -(int)unsigned_magnitude(y1 - y0);
    step_x = x0 < x1 ? 1 : -1;
    step_y = y0 < y1 ? 1 : -1;
    error = dx + dy;
    for (;;) {
        if (x0 >= 0 && x0 < (int)UDEKS_VIC_WIDTH &&
            y0 >= 0 && y0 < (int)UDEKS_VIC_HEIGHT) {
            PLOT_UNCHECKED(x0, y0, color);
        }
        if (x0 == x1 && y0 == y1) {
            break;
        }
        twice = error << 1;
        if (twice >= dy) {
            error += dy;
            x0 += step_x;
        }
        if (twice <= dx) {
            error += dx;
            y0 += step_y;
        }
    }
}

void udeks_vic_bitmap_rectangle(
    int x, int y, int width, int height, unsigned char color)
{
    if (width <= 0 || height <= 0) {
        return;
    }
    udeks_vic_bitmap_line(x, y, x + width - 1, y, color);
    udeks_vic_bitmap_line(
        x, y + height - 1, x + width - 1, y + height - 1, color);
    udeks_vic_bitmap_line(x, y, x, y + height - 1, color);
    udeks_vic_bitmap_line(
        x + width - 1, y, x + width - 1, y + height - 1, color);
}

void udeks_vic_bitmap_fill(
    int x, int y, int width, int height, unsigned char color)
{
    int row;
    int column;
    int last_x;
    int last_y;
    unsigned int pixel_offset;
    unsigned char pixel_mask;

    if (width <= 0 || height <= 0) {
        return;
    }
    last_x = x + width;
    last_y = y + height;
    if (x < 0) {
        x = 0;
    }
    if (y < 0) {
        y = 0;
    }
    if (last_x > (int)UDEKS_VIC_WIDTH) {
        last_x = UDEKS_VIC_WIDTH;
    }
    if (last_y > (int)UDEKS_VIC_HEIGHT) {
        last_y = UDEKS_VIC_HEIGHT;
    }
    for (row = y; row < last_y; ++row) {
        for (column = x; column < last_x; ++column) {
            PLOT_UNCHECKED(column, row, color);
        }
    }
}

void udeks_vic_bitmap_commit(void)
{
    unsigned char page;

    if (STATUS_BYTE(5) != UDEKS_VIC_GRAPHICS_ACTIVE) {
        return;
    }
    for (page = 0; page < UDEKS_VIC_BITMAP_PAGES; ++page) {
        if (dirty_pages[page] != 0) {
            udeks_vic_bitmap_commit_page(page);
            dirty_pages[page] = 0;
        }
    }
    increment_counter(21u);
}

unsigned char udeks_vic_graphics_start(void)
{
    unsigned char offset;
    unsigned char row;

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
    for (offset = 0; offset < UDEKS_VIC_BITMAP_PAGES; ++offset) {
        dirty_pages[offset] = 0;
    }
    for (row = 0; row < UDEKS_VIC_HEIGHT; ++row) {
        bitmap_rows[row] = bitmap_offset(0, row);
    }
    udeks_xclock_initialize();
    return UDEKS_VIC_GRAPHICS_OK;
}

unsigned char udeks_vic_graphics_poll(void)
{
    if (STATUS_BYTE(5) == UDEKS_VIC_GRAPHICS_ACTIVE) {
        update_pointer();
        udeks_xclock_poll();
    }
    return UDEKS_VIC_GRAPHICS_OK;
}

unsigned char udeks_vic_graphics_is_active(void)
{
    return STATUS_BYTE(5) == UDEKS_VIC_GRAPHICS_ACTIVE ? 1u : 0u;
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
    if (udeks_xclock_is_running() != 0) {
        udeks_xclock_stop();
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

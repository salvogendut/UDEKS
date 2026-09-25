/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/vic_graphics.h"
#include "udeks/memory.h"
#include "udeks/pointer.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_VIC_GRAPHICS_STATUS_BASE + (offset)))

extern unsigned char udeks_vic_graphics_enable(void);
extern unsigned char udeks_vic_graphics_disable(void);
extern void udeks_vic_pointer_set_x(unsigned int x);
extern void udeks_vic_pointer_set_y(unsigned char y);
extern void udeks_vic_pointer_busy_tick(void);
extern void udeks_vic_bitmap_commit_page(unsigned char page);
extern void udeks_vic_bitmap_outline_blit(void);

#pragma bss-name(push, "VICSHADOW")
unsigned char udeks_vic_bitmap_shadow[8192];
#pragma bss-name(pop)

#define bitmap_rows ((unsigned int *)UDEKS_VIC_ROW_TABLE_BASE)
#define dirty_pages ((unsigned char *)UDEKS_VIC_DIRTY_MAP_BASE)
#define clip_left (*(int *)(UDEKS_VIC_CLIP_STATE_BASE + 0u))
#define clip_top (*(int *)(UDEKS_VIC_CLIP_STATE_BASE + 2u))
#define clip_right (*(int *)(UDEKS_VIC_CLIP_STATE_BASE + 4u))
#define clip_bottom (*(int *)(UDEKS_VIC_CLIP_STATE_BASE + 6u))

#define OUTLINE_COUNT          (*(volatile unsigned char *)0xF37Fu)
#define OUTLINE_BUFFER         ((volatile unsigned char *)0xF380u)
#define OUTLINE_RECORD_SIZE    15u

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

    if (x < clip_left || x >= clip_right ||
        y < clip_top || y >= clip_bottom) {
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
        if (x0 >= clip_left && x0 < clip_right &&
            y0 >= clip_top && y0 < clip_bottom) {
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
    int last_x;
    int last_y;

    if (width <= 0 || height <= 0) {
        return;
    }
    last_x = x + width - 1;
    last_y = y + height - 1;
    udeks_vic_bitmap_line(x, y, last_x, y, color);
    udeks_vic_bitmap_line(x, last_y, last_x, last_y, color);
    udeks_vic_bitmap_line(x, y, x, last_y, color);
    udeks_vic_bitmap_line(last_x, y, last_x, last_y, color);
}

void udeks_vic_bitmap_fill(
    int x, int y, int width, int height, unsigned char color)
{
    int row;
    int last_x;
    int last_y;
    unsigned int left;
    unsigned int right;
    unsigned int offset;
    unsigned int final_offset;
    unsigned char first_mask;
    unsigned char last_mask;
    unsigned char mask;

    if (width <= 0 || height <= 0) {
        return;
    }
    last_x = x + width;
    last_y = y + height;
    if (x < clip_left) {
        x = clip_left;
    }
    if (y < clip_top) {
        y = clip_top;
    }
    if (last_x > clip_right) {
        last_x = clip_right;
    }
    if (last_y > clip_bottom) {
        last_y = clip_bottom;
    }
    if (x >= last_x || y >= last_y) {
        return;
    }
    left = (unsigned int)x;
    right = (unsigned int)(last_x - 1);
    first_mask = (unsigned char)(0xFFu >> (left & 7u));
    last_mask = (unsigned char)(0xFFu << (7u - (right & 7u)));
    for (row = y; row < last_y; ++row) {
        offset = (unsigned int)(bitmap_rows[(unsigned char)row] +
            (left & 0xFFF8u));
        final_offset = (unsigned int)(bitmap_rows[(unsigned char)row] +
            (right & 0xFFF8u));
        mask = first_mask;
        for (;;) {
            if (offset == final_offset) {
                mask &= last_mask;
            }
            if (color == UDEKS_VIC_COLOR_BLACK) {
                udeks_vic_bitmap_shadow[offset] |= mask;
            } else {
                udeks_vic_bitmap_shadow[offset] &= (unsigned char)~mask;
            }
            dirty_pages[offset >> 8] = 1;
            if (offset == final_offset) {
                break;
            }
            offset += 8u;
            mask = 0xFFu;
        }
    }
}

void udeks_vic_bitmap_set_clip(int x, int y, int width, int height)
{
    int right;
    int bottom;

    if (width <= 0 || height <= 0) {
        clip_left = 0;
        clip_top = 0;
        clip_right = 0;
        clip_bottom = 0;
        return;
    }
    right = x + width;
    bottom = y + height;
    clip_left = x < 0 ? 0 : x;
    clip_top = y < 0 ? 0 : y;
    clip_right = right > (int)UDEKS_VIC_WIDTH ?
        (int)UDEKS_VIC_WIDTH : right;
    clip_bottom = bottom > (int)UDEKS_VIC_HEIGHT ?
        (int)UDEKS_VIC_HEIGHT : bottom;
    if (clip_right < clip_left) {
        clip_right = clip_left;
    }
    if (clip_bottom < clip_top) {
        clip_bottom = clip_top;
    }
}

void udeks_vic_bitmap_reset_clip(void)
{
    clip_left = 0;
    clip_top = 0;
    clip_right = UDEKS_VIC_WIDTH;
    clip_bottom = UDEKS_VIC_HEIGHT;
}

static void outline_word(
    unsigned char base, unsigned char offset, unsigned int value)
{
    OUTLINE_BUFFER[base + offset] = (unsigned char)value;
    OUTLINE_BUFFER[base + offset + 1u] = (unsigned char)(value >> 8);
}

static void prepare_outline(
    unsigned char base, unsigned int x, unsigned char y,
    unsigned int width, unsigned char height)
{
    unsigned int right;
    unsigned char bottom;
    unsigned int address;

    right = x + width - 1u;
    bottom = (unsigned char)(y + height - 1u);
    address = (unsigned int)(0x6000u + bitmap_offset(x, y));
    outline_word(base, 0u, address);
    address = (unsigned int)(0x6000u + bitmap_offset(x, bottom));
    outline_word(base, 2u, address);
    OUTLINE_BUFFER[base + 4u] =
        (unsigned char)((right >> 3) - (x >> 3) + 1u);
    OUTLINE_BUFFER[base + 5u] =
        (unsigned char)(0xFFu >> (x & 7u));
    OUTLINE_BUFFER[base + 6u] =
        (unsigned char)(0xFFu << (7u - (right & 7u)));
    address = (unsigned int)(0x6000u + bitmap_offset(x, y + 1u));
    outline_word(base, 7u, address);
    OUTLINE_BUFFER[base + 9u] =
        (unsigned char)(0x80u >> (x & 7u));
    address = (unsigned int)(0x6000u + bitmap_offset(right, y + 1u));
    outline_word(base, 10u, address);
    OUTLINE_BUFFER[base + 12u] =
        (unsigned char)(0x80u >> (right & 7u));
    OUTLINE_BUFFER[base + 13u] = (unsigned char)(height - 2u);
    OUTLINE_BUFFER[base + 14u] = (unsigned char)((y + 1u) & 7u);
}

static unsigned char outline_valid(
    unsigned int x, unsigned char y,
    unsigned int width, unsigned char height)
{
    return width > 1u && height > 2u &&
        x + width <= UDEKS_VIC_WIDTH &&
        (unsigned int)y + height <= UDEKS_VIC_HEIGHT;
}

void udeks_vic_bitmap_outline_toggle(
    unsigned int x, unsigned char y,
    unsigned int width, unsigned char height)
{
    if (STATUS_BYTE(5) != UDEKS_VIC_GRAPHICS_ACTIVE ||
        outline_valid(x, y, width, height) == 0) {
        return;
    }
    prepare_outline(0u, x, y, width, height);
    OUTLINE_COUNT = 1u;
    udeks_vic_bitmap_outline_blit();
    increment_counter(21u);
}

void udeks_vic_bitmap_outline_move(
    unsigned int old_x, unsigned char old_y,
    unsigned int new_x, unsigned char new_y,
    unsigned int width, unsigned char height)
{
    if (STATUS_BYTE(5) != UDEKS_VIC_GRAPHICS_ACTIVE ||
        outline_valid(old_x, old_y, width, height) == 0 ||
        outline_valid(new_x, new_y, width, height) == 0) {
        return;
    }
    prepare_outline(0u, old_x, old_y, width, height);
    prepare_outline(OUTLINE_RECORD_SIZE, new_x, new_y, width, height);
    OUTLINE_COUNT = 2u;
    udeks_vic_bitmap_outline_blit();
    increment_counter(21u);
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
    udeks_vic_bitmap_reset_clip();
    return UDEKS_VIC_GRAPHICS_OK;
}

unsigned char udeks_vic_graphics_poll(void)
{
    if (STATUS_BYTE(5) == UDEKS_VIC_GRAPHICS_ACTIVE) {
        udeks_vic_pointer_busy_tick();
        update_pointer();
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

/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/font.h"
#include "udeks/framebuffer.h"
#include "udeks/framebuffer_surface.h"

#include <string.h>

#define DIRTY_MAP_STRIDE 10u
#define DIRTY_MAP_SIZE   2000u

static unsigned char pixels[UDEKS_FRAMEBUFFER_SIZE];
static unsigned char dirty_map[DIRTY_MAP_SIZE];
static unsigned char dirty_tracking;
static unsigned char dirty_first_row;
static unsigned char dirty_last_row;

static void mark_dirty(
    unsigned char y, unsigned char first, unsigned char last)
{
    unsigned int base;

    if (dirty_first_row >= UDEKS_FRAMEBUFFER_HEIGHT) {
        dirty_first_row = y;
        dirty_last_row = y;
    } else {
        if (y < dirty_first_row) {
            dirty_first_row = y;
        }
        if (y > dirty_last_row) {
            dirty_last_row = y;
        }
    }
    base = (unsigned int)y * DIRTY_MAP_STRIDE;
    while (first <= last) {
        dirty_map[base + (first >> 3)] |=
            (unsigned char)(0x80u >> (first & 7u));
        ++first;
    }
}

void udeks_surface_reset(void)
{
    memset(pixels, 0, sizeof(pixels));
    memset(dirty_map, 0, sizeof(dirty_map));
    dirty_first_row = UDEKS_FRAMEBUFFER_HEIGHT;
    dirty_last_row = 0;
    dirty_tracking = 1;
}

unsigned char udeks_surface_plot(
    unsigned int x, unsigned char y, unsigned char set)
{
    unsigned int offset;
    unsigned char column;
    unsigned char mask;
    unsigned char value;

    if (x >= 640u || y >= UDEKS_FRAMEBUFFER_HEIGHT) {
        return UDEKS_FRAMEBUFFER_OK;
    }
    column = (unsigned char)(x >> 3);
    mask = (unsigned char)(0x80u >> (x & 7u));
    offset = (unsigned int)y * UDEKS_FRAMEBUFFER_STRIDE + column;
    value = pixels[offset];
    if (set != 0) {
        value |= mask;
    } else {
        value &= (unsigned char)~mask;
    }
    if (value != pixels[offset]) {
        pixels[offset] = value;
        if (dirty_tracking != 0) {
            mark_dirty(y, column, column);
        }
    }
    return UDEKS_FRAMEBUFFER_OK;
}

unsigned char udeks_surface_hline(
    unsigned int x, unsigned char y, unsigned int width, unsigned char set)
{
    unsigned int end;
    unsigned int offset;
    unsigned char first;
    unsigned char last;
    unsigned char column;
    unsigned char mask;
    unsigned char value;
    unsigned char changed;

    if (y >= UDEKS_FRAMEBUFFER_HEIGHT || x >= 640u || width == 0) {
        return UDEKS_FRAMEBUFFER_OK;
    }
    if (width > 640u - x) {
        width = 640u - x;
    }
    end = x + width - 1u;
    first = (unsigned char)(x >> 3);
    last = (unsigned char)(end >> 3);
    offset = (unsigned int)y * UDEKS_FRAMEBUFFER_STRIDE + first;
    changed = 0;
    for (column = first; column <= last; ++column) {
        mask = 0xFFu;
        if (column == first) {
            mask &= (unsigned char)(0xFFu >> (x & 7u));
        }
        if (column == last) {
            mask &= (unsigned char)(0xFFu << (7u - (end & 7u)));
        }
        value = pixels[offset];
        if (set != 0) {
            value |= mask;
        } else {
            value &= (unsigned char)~mask;
        }
        if (value != pixels[offset]) {
            pixels[offset] = value;
            changed = 1;
        }
        ++offset;
    }
    if (changed != 0 && dirty_tracking != 0) {
        mark_dirty(y, first, last);
    }
    return UDEKS_FRAMEBUFFER_OK;
}

unsigned char udeks_surface_fill_rect(
    unsigned int x, unsigned char y, unsigned int width,
    unsigned int height, unsigned char set)
{
    if (x >= 640u || y >= UDEKS_FRAMEBUFFER_HEIGHT ||
        width == 0 || height == 0) {
        return UDEKS_FRAMEBUFFER_OK;
    }
    if (height > UDEKS_FRAMEBUFFER_HEIGHT - y) {
        height = UDEKS_FRAMEBUFFER_HEIGHT - y;
    }
    while (height != 0) {
        udeks_surface_hline(x, y, width, set);
        ++y;
        --height;
    }
    return UDEKS_FRAMEBUFFER_OK;
}

unsigned char udeks_surface_draw_char(
    unsigned int x, unsigned char y, unsigned char character)
{
    const unsigned char *glyph;
    unsigned char row;
    unsigned char column;
    unsigned char value;
    unsigned int offset;

    glyph = udeks_font_glyph(character);
    if ((x & 7u) == 0 && x <= 632u) {
        column = (unsigned char)(x >> 3);
        for (row = 0; row < UDEKS_FONT_CELL_HEIGHT; ++row) {
            if ((unsigned int)y + row >= UDEKS_FRAMEBUFFER_HEIGHT) {
                break;
            }
            value = row < UDEKS_FONT_HEIGHT ?
                (unsigned char)(glyph[row] << 3) : 0;
            offset = (unsigned int)(y + row) *
                UDEKS_FRAMEBUFFER_STRIDE + column;
            if (pixels[offset] != value) {
                pixels[offset] = value;
                if (dirty_tracking != 0) {
                    mark_dirty((unsigned char)(y + row), column, column);
                }
            }
        }
        return UDEKS_FRAMEBUFFER_OK;
    }

    for (row = 0; row < UDEKS_FONT_CELL_HEIGHT; ++row) {
        if ((unsigned int)y + row >= UDEKS_FRAMEBUFFER_HEIGHT) {
            break;
        }
        value = row < UDEKS_FONT_HEIGHT ?
            (unsigned char)(glyph[row] << 3) : 0;
        for (column = 0; column < UDEKS_FONT_CELL_WIDTH; ++column) {
            udeks_surface_plot(
                x + column, (unsigned char)(y + row),
                (unsigned char)(value & (0x80u >> column)));
        }
    }
    return UDEKS_FRAMEBUFFER_OK;
}

unsigned char udeks_surface_draw_text(
    unsigned int x, unsigned char y, const unsigned char *text)
{
    while (*text != 0 && x < 640u) {
        udeks_surface_draw_char(x, y, *text);
        x += UDEKS_FONT_CELL_WIDTH;
        ++text;
    }
    return UDEKS_FRAMEBUFFER_OK;
}

void udeks_surface_blit_packed(
    unsigned char x_byte, unsigned char y, unsigned char width_bytes,
    unsigned char height, const unsigned char *source)
{
    unsigned char row;
    unsigned char column;
    unsigned char copied;
    unsigned int offset;

    if (x_byte >= UDEKS_FRAMEBUFFER_STRIDE ||
        y >= UDEKS_FRAMEBUFFER_HEIGHT) {
        return;
    }
    for (row = 0; row < height; ++row) {
        if ((unsigned int)y + row >= UDEKS_FRAMEBUFFER_HEIGHT) {
            break;
        }
        copied = width_bytes;
        if ((unsigned int)x_byte + copied > UDEKS_FRAMEBUFFER_STRIDE) {
            copied = (unsigned char)(UDEKS_FRAMEBUFFER_STRIDE - x_byte);
        }
        offset = (unsigned int)(y + row) * UDEKS_FRAMEBUFFER_STRIDE + x_byte;
        for (column = 0; column < copied; ++column) {
            pixels[offset + column] = source[column];
        }
        if (copied != 0 && dirty_tracking != 0) {
            mark_dirty(y + row, x_byte, (unsigned char)(x_byte + copied - 1u));
        }
        source += width_bytes;
    }
}

unsigned char udeks_surface_dirty_span(
    unsigned char y, unsigned char start,
    unsigned char *first, unsigned char *last)
{
    unsigned int base;

    if (y >= UDEKS_FRAMEBUFFER_HEIGHT ||
        start >= UDEKS_FRAMEBUFFER_STRIDE) {
        return 0;
    }
    base = (unsigned int)y * DIRTY_MAP_STRIDE;
    while (start < UDEKS_FRAMEBUFFER_STRIDE &&
           (dirty_map[base + (start >> 3)] &
            (0x80u >> (start & 7u))) == 0) {
        ++start;
    }
    if (start == UDEKS_FRAMEBUFFER_STRIDE) {
        return 0;
    }
    *first = start;
    while (start + 1u < UDEKS_FRAMEBUFFER_STRIDE &&
           (dirty_map[base + ((start + 1u) >> 3)] &
            (0x80u >> ((start + 1u) & 7u))) != 0) {
        ++start;
    }
    *last = start;
    return 1;
}

unsigned char udeks_surface_byte(unsigned int offset)
{
    return pixels[offset];
}

unsigned char udeks_surface_dirty_bounds(
    unsigned char *first_row, unsigned char *last_row)
{
    if (dirty_first_row >= UDEKS_FRAMEBUFFER_HEIGHT) {
        return 0;
    }
    *first_row = dirty_first_row;
    *last_row = dirty_last_row;
    return 1;
}

const unsigned char *udeks_surface_data(void)
{
    return pixels;
}

void udeks_surface_set_dirty_tracking(unsigned char enabled)
{
    dirty_tracking = enabled != 0;
}

void udeks_surface_clean_span(
    unsigned char y, unsigned char first, unsigned char last)
{
    unsigned int base;

    base = (unsigned int)y * DIRTY_MAP_STRIDE;
    while (first <= last) {
        dirty_map[base + (first >> 3)] &=
            (unsigned char)~(0x80u >> (first & 7u));
        ++first;
    }
}

void udeks_surface_clean_all(void)
{
    memset(dirty_map, 0, sizeof(dirty_map));
    dirty_first_row = UDEKS_FRAMEBUFFER_HEIGHT;
    dirty_last_row = 0;
}

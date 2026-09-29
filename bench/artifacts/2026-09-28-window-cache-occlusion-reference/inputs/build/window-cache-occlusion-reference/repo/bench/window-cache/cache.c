/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Machine-level prototype, not linked into UDEKS. No yield or callback may
 * occur while $F400 contains staging bytes instead of its service code. */
#include "cache.h"
#define SHADOW ((unsigned char *)0xA1E0u)
#define STAGE ((volatile unsigned char *)0xF400u)
#define ADDRESS (*(volatile unsigned int *)0xF380u)
#define COUNT (*(volatile unsigned char *)0xF382u)
#define DIRTY ((unsigned char *)0xE190u)
#define CACHE_BASE 0x4200u
#define CACHE_BYTES 0x1A00u

static unsigned int saved_width;
static unsigned char saved_height;
static unsigned char stride;
static unsigned char valid;

static unsigned int row_offset(unsigned char y)
{
    return (unsigned int)(y & 248u) * 40u + (y & 7u);
}

unsigned char cache_capture(unsigned int x, unsigned char y,
                            unsigned int width, unsigned char height)
{
    static unsigned char row, column, shift, bytes, value;
    static unsigned int offset, source, cache_address;
    valid = 0;
    if (width == 0 || width > 320u || height == 0 || height > 200u ||
        x > 320u - width || y > 200u - height) return 0;
    bytes = (unsigned char)((width + 7u) >> 3);
    if ((unsigned int)bytes * height > CACHE_BYTES) return 0;
    saved_width = width;
    saved_height = height;
    stride = bytes;
    shift = (unsigned char)(x & 7u);
    cache_address = CACHE_BASE;
    for (row = 0; row < height; ++row) {
        offset = row_offset((unsigned char)(y + row)) + (x & 0xFFF8u);
        for (column = 0; column < bytes; ++column) {
            source = offset + (unsigned int)column * 8u;
            value = SHADOW[source];
            if (shift != 0) {
                value <<= shift;
                if ((x >> 3) + column < 39u)
                    value |= SHADOW[source + 8u] >> (8u - shift);
            }
            if (column == bytes - 1u && (width & 7u) != 0)
                value &= (unsigned char)~(0x7Fu >> ((width & 7u) - 1u));
            STAGE[column] = value;
        }
        ADDRESS = cache_address;
        COUNT = bytes;
        cache_transfer(0); /* common staging -> private bank-1 cache */
        cache_transfer(2); /* restore service page before leaving row */
        cache_address += bytes;
    }
    valid = 1;
    return 1;
}

unsigned char cache_paste(unsigned int x, unsigned char y)
{
    static unsigned char row, column, shift, mask, first, second, value, part;
    static unsigned int offset, target, cache_address;
    if (!valid || x > 320u - saved_width || y > 200u - saved_height) return 0;
    shift = (unsigned char)(x & 7u);
    cache_address = CACHE_BASE;
    for (row = 0; row < saved_height; ++row) {
        ADDRESS = cache_address;
        COUNT = stride;
        cache_transfer(1); /* private bank-1 cache -> common staging */
        offset = row_offset((unsigned char)(y + row)) + (x & 0xFFF8u);
        for (column = 0; column < stride; ++column) {
            value = STAGE[column];
            mask = 255u;
            if (column == stride - 1u && (saved_width & 7u) != 0)
                mask = (unsigned char)~(0x7Fu >> ((saved_width & 7u) - 1u));
            target = offset + (unsigned int)column * 8u;
            first = mask >> shift;
            SHADOW[target] = (SHADOW[target] & (unsigned char)~first) |
                            ((value >> shift) & first);
            DIRTY[target >> 8] = 1;
            if (shift != 0) {
                second = (unsigned char)(mask << (8u - shift));
                if (second != 0) {
                    part = (unsigned char)(value << (8u - shift));
                    SHADOW[target + 8u] =
                        (SHADOW[target + 8u] & (unsigned char)~second) |
                        (part & second);
                    DIRTY[(target + 8u) >> 8] = 1;
                }
            }
        }
        cache_transfer(2);
        cache_address += stride;
    }
    return 1;
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Standalone assembly-row variant. A complete operation owns the gateway and
 * staging page: no yield, callback, service dispatch or nested drawing. */
#include "cache.h"
#define ADDRESS (*(volatile unsigned int *)0xF380u)
#define COUNT (*(volatile unsigned char *)0xF382u)
#define CACHE_BASE 0x4200u
#define CACHE_BYTES 0x1A00u

unsigned int cache_row_offset;
unsigned char cache_row_shift, cache_row_next_count, cache_row_last_mask;
void cache_transfer_begin(void);
void __fastcall__ cache_transfer_fast(unsigned char mode);
void cache_capture_row(void);
void cache_paste_row(void);

static unsigned int saved_width;
static unsigned char saved_height, stride, valid;
static unsigned char row;
static unsigned int cache_address;

static unsigned int row_offset(unsigned char y)
{
    return (unsigned int)(y & 248u) * 40u + (y & 7u);
}

static void row_parameters(unsigned int x, unsigned int width)
{
    cache_row_shift = (unsigned char)(x & 7u);
    cache_row_next_count = (unsigned char)(39u - (x >> 3));
    cache_row_last_mask = 255u;
    if ((width & 7u) != 0)
        cache_row_last_mask = (unsigned char)~(0x7Fu >> ((width & 7u) - 1u));
}

unsigned char cache_capture(unsigned int x, unsigned char y,
                            unsigned int width, unsigned char height)
{
    valid = 0;
    if (width == 0 || width > 320u || height == 0 || height > 200u ||
        x > 320u - width || y > 200u - height) return 0;
    stride = (unsigned char)((width + 7u) >> 3);
    if ((unsigned int)stride * height > CACHE_BYTES) return 0;
    saved_width = width;
    saved_height = height;
    row_parameters(x, width);
    cache_address = CACHE_BASE;
    cache_transfer_begin();
    COUNT = stride;
    for (row = 0; row < height; ++row) {
        cache_row_offset = row_offset((unsigned char)(y + row)) + (x & 0xFFF8u);
        cache_capture_row();
        ADDRESS = cache_address;
        cache_transfer_fast(0);
        cache_address += stride;
    }
    cache_transfer_fast(2);
    valid = 1;
    return 1;
}

unsigned char cache_paste(unsigned int x, unsigned char y)
{
    if (!valid || x > 320u - saved_width || y > 200u - saved_height) return 0;
    row_parameters(x, saved_width);
    cache_address = CACHE_BASE;
    cache_transfer_begin();
    COUNT = stride;
    for (row = 0; row < saved_height; ++row) {
        ADDRESS = cache_address;
        cache_transfer_fast(1);
        cache_row_offset = row_offset((unsigned char)(y + row)) + (x & 0xFFF8u);
        cache_paste_row();
        cache_address += stride;
    }
    cache_transfer_fast(2);
    return 1;
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private, compiler-local window-service policy. Not a syscall or wire ABI.
 * Not yet linked into the resident kernel or bank-1 display overlay. */
#ifndef UDEKS_WINDOW_CACHE_STATE_H
#define UDEKS_WINDOW_CACHE_STATE_H
#include <stdint.h>

#define UDEKS_CACHE_EMPTY       0u
#define UDEKS_CACHE_CAPTURING   1u
#define UDEKS_CACHE_READY       2u
#define UDEKS_CACHE_PASTING     3u
#define UDEKS_CACHE_OK          0u
#define UDEKS_CACHE_INVALID     1u
#define UDEKS_CACHE_BUSY        2u

struct udeks_cache_geometry {
    uint16_t x, width;
    uint8_t y, height;
};

struct udeks_cache_lease {
    struct udeks_cache_geometry geometry;
    uint16_t generation, capacity;
    uint8_t owner, phase, row;
};

struct udeks_cache_row {
    uint16_t shadow_offset, image_offset;
    uint8_t stride, raw_count, shift, last_mask, mode;
};

void udeks_cache_init(struct udeks_cache_lease *lease, uint16_t capacity);
void udeks_cache_invalidate(struct udeks_cache_lease *lease, uint8_t owner);
uint8_t udeks_cache_capture_begin(struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation,
    const struct udeks_cache_geometry *geometry, uint8_t eligible);
uint8_t udeks_cache_paste_begin(struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation,
    const struct udeks_cache_geometry *geometry);
uint8_t udeks_cache_prepare_row(const struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation, struct udeks_cache_row *output);
uint8_t udeks_cache_commit_row(struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation, uint8_t row);
#endif

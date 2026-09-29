/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Pure C policy; no hardware, drawing, callbacks, bank switching or polling.
 * Caller owns serialization and explicit completion/visibility notification.
 * Capture must freeze the source for its entire continuation, not just a row.
 * Rejected operations leave both lease and row output unchanged. */
#include "udeks/window_cache_state.h"
#ifdef UDEKS_CACHE_COMMAND_HOST_TEST
extern struct udeks_cache_lease cache_test_lease;
#define FIXED (&cache_test_lease)
#else
#define FIXED ((struct udeks_cache_lease *)UDEKS_CACHE_LEASE_ADDRESS)
#endif

static uint8_t valid_geometry(const struct udeks_cache_geometry *g,
                              uint16_t capacity)
{
    uint16_t size;
    if (g->width == 0 || g->width > 320u ||
        g->height == 0 || g->height > 200u ||
        g->x > 320u - g->width || g->y > 200u - g->height) return 0;
    /* The product is at most 40*200=8000 on both host and 16-bit cc65. */
    size = ((g->width + 7u) >> 3) * g->height;
    return size <= capacity;
}

static uint8_t current_owner(const struct udeks_cache_lease *lease,
                             uint8_t owner, uint16_t generation)
{
    return lease == FIXED && owner != 0 && owner <= 4u && generation != 0 &&
        FIXED->owner == owner && FIXED->generation == generation;
}

void udeks_cache_init(struct udeks_cache_lease *lease, uint16_t capacity)
{
    if (lease != FIXED) return;
    FIXED->geometry.x = 0;
    FIXED->geometry.width = 0;
    FIXED->geometry.y = 0;
    FIXED->geometry.height = 0;
    FIXED->generation = 0;
    FIXED->capacity = capacity;
    FIXED->owner = 0;
    FIXED->phase = UDEKS_CACHE_EMPTY;
    FIXED->row = 0;
}

void udeks_cache_invalidate(struct udeks_cache_lease *lease, uint8_t owner)
{
    if (lease != FIXED) return;
    if (owner == 0 || FIXED->owner == owner)
        udeks_cache_init(lease, FIXED->capacity);
}

uint8_t udeks_cache_capture_begin(struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation,
    const struct udeks_cache_geometry *geometry, uint8_t eligible)
{
    if (lease != FIXED || owner == 0 || owner > 4u || generation == 0 || eligible != 1u ||
        !valid_geometry(geometry, FIXED->capacity)) return UDEKS_CACHE_INVALID;
    if (FIXED->phase == UDEKS_CACHE_CAPTURING ||
        FIXED->phase == UDEKS_CACHE_PASTING) return UDEKS_CACHE_BUSY;
    FIXED->geometry = *geometry;
    FIXED->owner = owner;
    FIXED->generation = generation;
    FIXED->phase = UDEKS_CACHE_CAPTURING;
    FIXED->row = 0;
    return UDEKS_CACHE_OK;
}

uint8_t udeks_cache_paste_begin(struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation,
    const struct udeks_cache_geometry *geometry)
{
    if (!current_owner(lease, owner, generation) ||
        FIXED->phase != UDEKS_CACHE_READY ||
        geometry->width != FIXED->geometry.width ||
        geometry->height != FIXED->geometry.height ||
        !valid_geometry(geometry, FIXED->capacity)) return UDEKS_CACHE_INVALID;
    FIXED->geometry.x = geometry->x;
    FIXED->geometry.y = geometry->y;
    FIXED->phase = UDEKS_CACHE_PASTING;
    FIXED->row = 0;
    return UDEKS_CACHE_OK;
}

uint8_t udeks_cache_prepare_row(const struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation, struct udeks_cache_row *output)
{
    uint8_t y, shift, stride, bits;
    if (!current_owner(lease, owner, generation) ||
        (FIXED->phase != UDEKS_CACHE_CAPTURING &&
         FIXED->phase != UDEKS_CACHE_PASTING) ||
        FIXED->row >= FIXED->geometry.height) return UDEKS_CACHE_INVALID;
    y = FIXED->geometry.y + FIXED->row;
    shift = FIXED->geometry.x & 7u;
    stride = (FIXED->geometry.width + 7u) >> 3;
    bits = FIXED->geometry.width & 7u;
    output->shadow_offset = (uint16_t)(y & 248u) * 40u +
        (y & 7u) + (FIXED->geometry.x & 0xFFF8u);
    output->image_offset = (uint16_t)FIXED->row * stride;
    output->stride = stride;
    output->raw_count = (FIXED->geometry.width + shift + 7u) >> 3;
    output->shift = shift;
    output->last_mask = bits ? (uint8_t)(255u << (8u - bits)) : 255u;
    output->mode = FIXED->phase == UDEKS_CACHE_PASTING ? 1u : 0u;
    return UDEKS_CACHE_OK;
}

uint8_t udeks_cache_commit_row(struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation, uint8_t row)
{
    if (!current_owner(lease, owner, generation) ||
        (FIXED->phase != UDEKS_CACHE_CAPTURING &&
         FIXED->phase != UDEKS_CACHE_PASTING) || row != FIXED->row ||
        row >= FIXED->geometry.height) return UDEKS_CACHE_INVALID;
    ++FIXED->row;
    if (FIXED->row == FIXED->geometry.height) FIXED->phase = UDEKS_CACHE_READY;
    return UDEKS_CACHE_OK;
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Pure C policy; no hardware, drawing, callbacks, bank switching or polling.
 * Caller owns serialization and explicit completion/visibility notification.
 * Capture must freeze the source for its entire continuation, not just a row.
 * Rejected operations leave both lease and row output unchanged. */
#include "udeks/window_cache_state.h"

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
    return owner != 0 && owner <= 4u && generation != 0 &&
        lease->owner == owner && lease->generation == generation;
}

void udeks_cache_init(struct udeks_cache_lease *lease, uint16_t capacity)
{
    lease->geometry.x = 0;
    lease->geometry.width = 0;
    lease->geometry.y = 0;
    lease->geometry.height = 0;
    lease->generation = 0;
    lease->capacity = capacity;
    lease->owner = 0;
    lease->phase = UDEKS_CACHE_EMPTY;
    lease->row = 0;
}

void udeks_cache_invalidate(struct udeks_cache_lease *lease, uint8_t owner)
{
    if (owner == 0 || lease->owner == owner)
        udeks_cache_init(lease, lease->capacity);
}

uint8_t udeks_cache_capture_begin(struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation,
    const struct udeks_cache_geometry *geometry, uint8_t eligible)
{
    if (owner == 0 || owner > 4u || generation == 0 || eligible != 1u ||
        !valid_geometry(geometry, lease->capacity)) return UDEKS_CACHE_INVALID;
    if (lease->phase == UDEKS_CACHE_CAPTURING ||
        lease->phase == UDEKS_CACHE_PASTING) return UDEKS_CACHE_BUSY;
    lease->geometry = *geometry;
    lease->owner = owner;
    lease->generation = generation;
    lease->phase = UDEKS_CACHE_CAPTURING;
    lease->row = 0;
    return UDEKS_CACHE_OK;
}

uint8_t udeks_cache_paste_begin(struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation,
    const struct udeks_cache_geometry *geometry)
{
    if (!current_owner(lease, owner, generation) ||
        lease->phase != UDEKS_CACHE_READY ||
        geometry->width != lease->geometry.width ||
        geometry->height != lease->geometry.height ||
        !valid_geometry(geometry, lease->capacity)) return UDEKS_CACHE_INVALID;
    lease->geometry.x = geometry->x;
    lease->geometry.y = geometry->y;
    lease->phase = UDEKS_CACHE_PASTING;
    lease->row = 0;
    return UDEKS_CACHE_OK;
}

uint8_t udeks_cache_prepare_row(const struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation, struct udeks_cache_row *output)
{
    uint8_t y, shift, stride, bits;
    if (!current_owner(lease, owner, generation) ||
        (lease->phase != UDEKS_CACHE_CAPTURING &&
         lease->phase != UDEKS_CACHE_PASTING) ||
        lease->row >= lease->geometry.height) return UDEKS_CACHE_INVALID;
    y = lease->geometry.y + lease->row;
    shift = lease->geometry.x & 7u;
    stride = (lease->geometry.width + 7u) >> 3;
    bits = lease->geometry.width & 7u;
    output->shadow_offset = (uint16_t)(y & 248u) * 40u +
        (y & 7u) + (lease->geometry.x & 0xFFF8u);
    output->image_offset = (uint16_t)lease->row * stride;
    output->stride = stride;
    output->raw_count = (lease->geometry.width + shift + 7u) >> 3;
    output->shift = shift;
    output->last_mask = bits ? (uint8_t)(255u << (8u - bits)) : 255u;
    output->mode = lease->phase == UDEKS_CACHE_PASTING ? 1u : 0u;
    return UDEKS_CACHE_OK;
}

uint8_t udeks_cache_commit_row(struct udeks_cache_lease *lease,
    uint8_t owner, uint16_t generation, uint8_t row)
{
    if (!current_owner(lease, owner, generation) ||
        (lease->phase != UDEKS_CACHE_CAPTURING &&
         lease->phase != UDEKS_CACHE_PASTING) || row != lease->row ||
        row >= lease->geometry.height) return UDEKS_CACHE_INVALID;
    ++lease->row;
    if (lease->row == lease->geometry.height) lease->phase = UDEKS_CACHE_READY;
    return UDEKS_CACHE_OK;
}

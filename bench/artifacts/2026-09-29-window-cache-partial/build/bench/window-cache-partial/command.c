/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Bank-1 C service. Only the bounded row primitive enters common RAM. */
#include "udeks/window_cache_command.h"

#ifndef UDEKS_CACHE_LEASE_ADDRESS
#define UDEKS_CACHE_LEASE_ADDRESS 0x4EE0u
#define UDEKS_CACHE_ROW_ADDRESS 0x4EEDu
#define UDEKS_CACHE_IMAGE_ADDRESS 0x5000u
#endif

#ifdef UDEKS_CACHE_COMMAND_HOST_TEST
extern struct udeks_cache_lease cache_test_lease;
extern struct udeks_cache_row cache_test_row;
extern struct udeks_cache_geometry cache_test_geometry;
extern uint8_t cache_test_owner, cache_test_eligible, cache_test_params[14];
extern uint16_t cache_test_generation;
#define LEASE (&cache_test_lease)
#define ROW (&cache_test_row)
#define GEOMETRY (&cache_test_geometry)
#define OWNER cache_test_owner
#define GENERATION cache_test_generation
#define ELIGIBLE cache_test_eligible
#define PARAM cache_test_params
#else
#define LEASE ((struct udeks_cache_lease *)UDEKS_CACHE_LEASE_ADDRESS)
#define ROW ((struct udeks_cache_row *)UDEKS_CACHE_ROW_ADDRESS)
#define GEOMETRY ((const struct udeks_cache_geometry *)0xF7A1u)
#define OWNER (*(volatile uint8_t *)0xF792u)
#define GENERATION (*(volatile uint16_t *)0xF793u)
#define ELIGIBLE (*(volatile uint8_t *)0xF795u)
#define PARAM ((volatile uint8_t *)0xF780u)
#endif
extern void udeks_cache_overlay_row(void);
/* Three initialized DATA bytes, inside the checksummed module allocation.
 * Full-image geometry/stride remains authoritative for source addressing. */
uint8_t cache_partial_end = 0;
uint16_t cache_partial_width = 0;

uint8_t __fastcall__ udeks_cache_overlay_command(uint8_t command)
{
    uint8_t status;
    uint8_t written;
    uint16_t address;

    switch (command) {
    case UDEKS_CACHE_COMMAND_INIT:
        cache_partial_end = 0; cache_partial_width = 0;
        udeks_cache_init(LEASE, UDEKS_CACHE_IMAGE_CAPACITY);
        break;
    case UDEKS_CACHE_COMMAND_INVALIDATE:
        udeks_cache_invalidate(LEASE, OWNER);
        if (LEASE->phase == UDEKS_CACHE_EMPTY) {
            cache_partial_end = 0; cache_partial_width = 0;
        }
        break;
    case UDEKS_CACHE_COMMAND_CAPTURE:
        status = udeks_cache_capture_begin(LEASE, OWNER, GENERATION,
                                          GEOMETRY, ELIGIBLE);
        if (status != UDEKS_CACHE_OK) return status;
        break;
    case UDEKS_CACHE_COMMAND_PASTE:
        status = udeks_cache_paste_begin(LEASE, OWNER, GENERATION, GEOMETRY);
        if (status != UDEKS_CACHE_OK) return status;
        break;
    case UDEKS_CACHE_COMMAND_STEP:
        if (LEASE->phase == UDEKS_CACHE_PASTING &&
            (cache_partial_end <= LEASE->row ||
             cache_partial_end > LEASE->geometry.height ||
             cache_partial_width == 0 ||
             cache_partial_width > LEASE->geometry.width))
            return UDEKS_CACHE_INVALID;
        status = udeks_cache_prepare_row(LEASE, OWNER, GENERATION, ROW);
        if (status != UDEKS_CACHE_OK) return status;
        /* Prepare validated all inputs before touching common row parameters
         * or pixels. The row routine is synchronous and infallible within the
         * qualified lease; acknowledge only after it returns. */
        if (ROW->mode) {
            ROW->stride = (cache_partial_width + 7u) >> 3;
            ROW->raw_count = (cache_partial_width + ROW->shift + 7u) >> 3;
            ROW->last_mask = (cache_partial_width & 7u) ?
                (uint8_t)(255u << (8u - (cache_partial_width & 7u))) : 255u;
        }
        address = UDEKS_CACHE_IMAGE_ADDRESS + ROW->image_offset;
        PARAM[0] = (uint8_t)ROW->shadow_offset;
        PARAM[1] = (uint8_t)(ROW->shadow_offset >> 8);
        PARAM[2] = (uint8_t)address;
        PARAM[3] = (uint8_t)(address >> 8);
        PARAM[4] = ROW->stride;
        PARAM[5] = ROW->raw_count;
        PARAM[6] = ROW->shift;
        PARAM[7] = ROW->last_mask;
        PARAM[8] = ROW->mode;
        written = ROW->mode ? UDEKS_CACHE_COMMAND_WRITTEN : 0u;
        udeks_cache_overlay_row();
        status = udeks_cache_commit_row(LEASE, OWNER, GENERATION, LEASE->row);
        if (status != UDEKS_CACHE_OK) return status;
        if (ROW->mode && LEASE->row == cache_partial_end)
            LEASE->phase = UDEKS_CACHE_READY;
        return UDEKS_CACHE_COMMAND_SUCCESS | written | LEASE->phase;
    case UDEKS_CACHE_COMMAND_READY:
        if (OWNER == 0 || OWNER > 4u || GENERATION == 0 ||
            LEASE->owner != OWNER || LEASE->generation != GENERATION ||
            LEASE->phase != UDEKS_CACHE_READY ||
            LEASE->geometry.width != GEOMETRY->width ||
            LEASE->geometry.height != GEOMETRY->height)
            return UDEKS_CACHE_INVALID;
        break;
    default:
        return UDEKS_CACHE_INVALID;
    }
    if (command == UDEKS_CACHE_COMMAND_PASTE) {
        cache_partial_end = LEASE->geometry.height;
        cache_partial_width = LEASE->geometry.width;
    } else if (command == UDEKS_CACHE_COMMAND_CAPTURE) {
        cache_partial_end = 0; cache_partial_width = 0;
    }
    return UDEKS_CACHE_COMMAND_SUCCESS | LEASE->phase;
}

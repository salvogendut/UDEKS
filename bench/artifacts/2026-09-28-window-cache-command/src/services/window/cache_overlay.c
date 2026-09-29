/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Bank-1 C service. Only the bounded row primitive enters common RAM. */
#include "udeks/window_cache_command.h"

#ifdef UDEKS_CACHE_COMMAND_HOST_TEST
extern struct udeks_cache_lease cache_test_lease;
extern struct udeks_cache_row cache_test_row;
extern struct udeks_cache_geometry cache_test_geometry;
extern uint8_t cache_test_owner, cache_test_eligible, cache_test_params[9];
extern uint16_t cache_test_generation;
#define LEASE (&cache_test_lease)
#define ROW (&cache_test_row)
#define GEOMETRY (&cache_test_geometry)
#define OWNER cache_test_owner
#define GENERATION cache_test_generation
#define ELIGIBLE cache_test_eligible
#define PARAM cache_test_params
#else
#define LEASE ((struct udeks_cache_lease *)0x4EE0u)
#define ROW ((struct udeks_cache_row *)0x4EEDu)
#define GEOMETRY ((const struct udeks_cache_geometry *)0xF7A1u)
#define OWNER (*(volatile uint8_t *)0xF792u)
#define GENERATION (*(volatile uint16_t *)0xF793u)
#define ELIGIBLE (*(volatile uint8_t *)0xF795u)
#define PARAM ((volatile uint8_t *)0xF780u)
#endif
extern void udeks_cache_overlay_row(void);

uint8_t __fastcall__ udeks_cache_overlay_command(uint8_t command)
{
    uint8_t status;
    uint8_t written;
    uint16_t address;

    switch (command) {
    case UDEKS_CACHE_COMMAND_INIT:
        udeks_cache_init(LEASE, UDEKS_CACHE_IMAGE_CAPACITY);
        break;
    case UDEKS_CACHE_COMMAND_INVALIDATE:
        udeks_cache_invalidate(LEASE, OWNER);
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
        status = udeks_cache_prepare_row(LEASE, OWNER, GENERATION, ROW);
        if (status != UDEKS_CACHE_OK) return status;
        /* Prepare validated all inputs before touching common row parameters
         * or pixels. The row routine is synchronous and infallible within the
         * qualified lease; acknowledge only after it returns. */
        address = 0x5000u + ROW->image_offset;
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
    return UDEKS_CACHE_COMMAND_SUCCESS | LEASE->phase;
}

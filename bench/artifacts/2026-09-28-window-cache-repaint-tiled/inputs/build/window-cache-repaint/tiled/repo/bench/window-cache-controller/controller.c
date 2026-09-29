/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private diagnostic protocol 0.1. One outer runtime lease, no callbacks. */
#include "udeks/window_cache_flow.h"
#include "udeks/window_cache_command.h"
#define FLOW ((struct udeks_cache_flow *)UDEKS_CACHE_FLOW_ADDRESS)
#ifdef UDEKS_CACHE_CONTROLLER_HOST_TEST
extern uint8_t cache_test_owner, cache_test_eligible, controller_test_phase;
extern uint16_t cache_test_generation;
extern struct udeks_cache_geometry cache_test_geometry;
#define OWNER cache_test_owner
#define TICKET cache_test_generation
#define ELIGIBLE cache_test_eligible
#define GEOMETRY (&cache_test_geometry)
#define PHASE controller_test_phase
#else
#define OWNER (*(volatile uint8_t *)0xF792u)
#define TICKET (*(volatile uint16_t *)0xF793u)
#define ELIGIBLE (*(volatile uint8_t *)0xF795u)
#define GEOMETRY ((const struct udeks_cache_geometry *)0xF7A1u)
#define PHASE (*(volatile uint8_t *)0xF791u)
#endif

uint8_t __fastcall__ udeks_cache_controller(uint8_t op)
{
    uint8_t status;
    switch (op) {
    case UDEKS_CACHE_COMMAND_INIT:
        status = udeks_cache_flow_init(FLOW);
        break;
    case UDEKS_CACHE_COMMAND_INVALIDATE:
        udeks_cache_flow_invalidate(FLOW);
        status = UDEKS_CACHE_OK;
        break;
    case UDEKS_CACHE_COMMAND_CAPTURE:
        status = udeks_cache_flow_capture(FLOW, OWNER, GEOMETRY, ELIGIBLE);
        break;
    case UDEKS_CACHE_COMMAND_PASTE:
        status = udeks_cache_flow_paste(FLOW, OWNER, GEOMETRY);
        break;
    case UDEKS_CACHE_COMMAND_STEP:
        status = udeks_cache_flow_step(FLOW, OWNER, TICKET);
        break;
    default:
        return UDEKS_CACHE_INVALID;
    }
    if (status == UDEKS_CACHE_OK) {
        /* Publish the content ticket only on success. A rejected STEP must
         * not rewrite the caller's stale/cross-owner request. */
        TICKET = FLOW->generation;
        PHASE = FLOW->phase;
    }
    return status;
}

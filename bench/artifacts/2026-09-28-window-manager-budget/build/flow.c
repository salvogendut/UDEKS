/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Budget/host-test prototype only. No normal build invokes these entries. */
#include "udeks/window_cache_flow.h"
#include "udeks/window_cache_command.h"

#ifdef UDEKS_CACHE_FLOW_HOST_TEST
extern uint8_t flow_test_opcode, flow_test_handle, flow_test_eligible;
extern uint16_t flow_test_generation;
extern struct udeks_cache_geometry flow_test_geometry;
#define OP flow_test_opcode
#define HANDLE flow_test_handle
#define GENERATION flow_test_generation
#define ELIGIBLE flow_test_eligible
#define GEOMETRY flow_test_geometry
#else
#define OP (*(volatile uint8_t *)0xF790u)
#define HANDLE (*(volatile uint8_t *)0xF792u)
#define GENERATION (*(volatile uint16_t *)0xF793u)
#define ELIGIBLE (*(volatile uint8_t *)0xF795u)
#define GEOMETRY (*(volatile struct udeks_cache_geometry *)0xF7A1u)
#endif
extern uint8_t private_cache_policy_call(void);

static uint8_t command(const struct udeks_cache_flow *flow, uint8_t op)
{
    HANDLE = flow->handle;
    GENERATION = flow->generation;
    OP = op;
    return private_cache_policy_call();
}

static void geometry_request(const struct udeks_cache_geometry *geometry)
{
    GEOMETRY.x = geometry->x;
    GEOMETRY.width = geometry->width;
    GEOMETRY.y = geometry->y;
    GEOMETRY.height = geometry->height;
}

uint8_t udeks_cache_flow_init(struct udeks_cache_flow *flow)
{
    flow->generation = 1;
    flow->handle = 0;
    flow->phase = UDEKS_CACHE_EMPTY;
    return command(flow, UDEKS_CACHE_COMMAND_INIT) == 0x80u ?
        UDEKS_CACHE_OK : UDEKS_CACHE_INVALID;
}

void udeks_cache_flow_invalidate(struct udeks_cache_flow *flow)
{
    uint16_t next;
    flow->handle = 0; /* Invalidate ALL before a handle or generation is reused. */
    command(flow, UDEKS_CACHE_COMMAND_INVALIDATE);
    next = flow->generation + 1u;
    if (next == 0) next = 1;
    flow->generation = next;
    flow->phase = UDEKS_CACHE_EMPTY;
}

uint8_t udeks_cache_flow_capture(struct udeks_cache_flow *flow,
    uint8_t handle, const struct udeks_cache_geometry *geometry, uint8_t eligible)
{
    uint8_t result;
    uint8_t old_handle;
    if (handle == 0 || handle > 4 || flow->generation == 0 || !eligible || geometry == 0)
        return UDEKS_CACHE_INVALID;
    if (flow->phase == UDEKS_CACHE_CAPTURING || flow->phase == UDEKS_CACHE_PASTING)
        return UDEKS_CACHE_BUSY;
    if (flow->phase != UDEKS_CACHE_EMPTY && flow->phase != UDEKS_CACHE_READY)
        return UDEKS_CACHE_INVALID;
    geometry_request(geometry);
    ELIGIBLE = eligible;
    old_handle = flow->handle;
    flow->handle = handle;
    result = command(flow, UDEKS_CACHE_COMMAND_CAPTURE);
    if (result != 0x81u) {
        flow->handle = old_handle;
        return UDEKS_CACHE_INVALID;
    }
    flow->phase = UDEKS_CACHE_CAPTURING;
    return UDEKS_CACHE_OK;
}

uint8_t udeks_cache_flow_paste(struct udeks_cache_flow *flow,
    uint8_t handle, const struct udeks_cache_geometry *geometry)
{
    if (handle == 0 || handle > 4 || handle != flow->handle || geometry == 0 ||
        flow->generation == 0 || flow->phase != UDEKS_CACHE_READY)
        return UDEKS_CACHE_INVALID;
    geometry_request(geometry);
    if (command(flow, UDEKS_CACHE_COMMAND_PASTE) != 0x83u)
        return UDEKS_CACHE_INVALID;
    flow->phase = UDEKS_CACHE_PASTING;
    return UDEKS_CACHE_OK;
}

uint8_t udeks_cache_flow_step(struct udeks_cache_flow *flow,
    uint8_t handle, uint16_t generation)
{
    uint8_t result;
    if (handle == 0 || handle != flow->handle || generation == 0 ||
        generation != flow->generation ||
        (flow->phase != UDEKS_CACHE_CAPTURING && flow->phase != UDEKS_CACHE_PASTING))
        return UDEKS_CACHE_INVALID;
    result = command(flow, UDEKS_CACHE_COMMAND_STEP);
    /* Keep phase comparisons scalar. The equivalent variable bitmask form
     * crashes the reference cc65 optimizer; exact constants also reject a
     * missing or spurious WRITTEN bit without accepting other phases. */
    if (flow->phase == UDEKS_CACHE_CAPTURING) {
        if (result == 0x81u) return UDEKS_CACHE_OK;
        if (result != 0x82u) goto failed;
    } else {
        if (result == 0xC3u) return UDEKS_CACHE_OK;
        if (result != 0xC2u) goto failed;
    }
    flow->phase = UDEKS_CACHE_READY;
    return UDEKS_CACHE_OK;
failed:
    udeks_cache_flow_invalidate(flow); /* Caller must repaint on backend failure. */
    return UDEKS_CACHE_INVALID;
}

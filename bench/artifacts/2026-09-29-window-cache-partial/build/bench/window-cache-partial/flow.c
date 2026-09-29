/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Budget/host-test prototype only. No normal build invokes these entries. */
#include "udeks/window_cache_flow.h"
#include "udeks/window_cache_command.h"

/* A banked module owns exactly one flow. Its fixed-address specialization
 * avoids indirect struct access on the 6502; callers must pass that same
 * private state address. Host/resident prototypes remain caller-owned. */
#ifdef UDEKS_CACHE_FLOW_ADDRESS
#define STATE ((struct udeks_cache_flow *)UDEKS_CACHE_FLOW_ADDRESS)
#else
#define STATE flow
#endif

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
#ifndef UDEKS_CACHE_FLOW_IN_BANK
extern uint8_t private_cache_policy_call(void);
#endif

static uint8_t command(const struct udeks_cache_flow *flow, uint8_t op)
{
    (void)flow; /* Fixed-state specialization still shares the generic API. */
    HANDLE = STATE->handle;
    GENERATION = STATE->generation;
    OP = op;
#ifdef UDEKS_CACHE_FLOW_IN_BANK
    /* The outer gateway already owns MMU, IRQ and runtime state. Re-entering
     * that gateway here would reset the live software stack. */
    return udeks_cache_overlay_command(op);
#else
    return private_cache_policy_call();
#endif
}

static void geometry_request(const struct udeks_cache_geometry *geometry)
{
    (void)geometry; /* Caller must supply the shared request record itself. */
}

uint8_t udeks_cache_flow_init(struct udeks_cache_flow *flow)
{
    STATE->generation = 1;
    STATE->handle = 0;
    STATE->phase = UDEKS_CACHE_EMPTY;
    return command(flow, UDEKS_CACHE_COMMAND_INIT) == 0x80u ?
        UDEKS_CACHE_OK : UDEKS_CACHE_INVALID;
}

void udeks_cache_flow_invalidate(struct udeks_cache_flow *flow)
{
    uint16_t next;
    STATE->handle = 0; /* Invalidate ALL before a handle or generation is reused. */
    command(flow, UDEKS_CACHE_COMMAND_INVALIDATE);
    next = STATE->generation + 1u;
    if (next == 0) next = 1;
    STATE->generation = next;
    STATE->phase = UDEKS_CACHE_EMPTY;
}

uint8_t udeks_cache_flow_capture(struct udeks_cache_flow *flow,
    uint8_t handle, const struct udeks_cache_geometry *geometry, uint8_t eligible)
{
    uint8_t result;
    uint8_t old_handle;
    if (handle == 0 || handle > 4 || STATE->generation == 0 || !eligible || geometry != (const struct udeks_cache_geometry *)&GEOMETRY)
        return UDEKS_CACHE_INVALID;
    if (STATE->phase == UDEKS_CACHE_CAPTURING || STATE->phase == UDEKS_CACHE_PASTING)
        return UDEKS_CACHE_BUSY;
    if (STATE->phase != UDEKS_CACHE_EMPTY && STATE->phase != UDEKS_CACHE_READY)
        return UDEKS_CACHE_INVALID;
    geometry_request(geometry);
    ELIGIBLE = eligible;
    old_handle = STATE->handle;
    STATE->handle = handle;
    result = command(flow, UDEKS_CACHE_COMMAND_CAPTURE);
    if (result != 0x81u) {
        STATE->handle = old_handle;
        return UDEKS_CACHE_INVALID;
    }
    STATE->phase = UDEKS_CACHE_CAPTURING;
    return UDEKS_CACHE_OK;
}

uint8_t udeks_cache_flow_paste(struct udeks_cache_flow *flow,
    uint8_t handle, const struct udeks_cache_geometry *geometry)
{
    if (handle == 0 || handle > 4 || handle != STATE->handle || geometry != (const struct udeks_cache_geometry *)&GEOMETRY ||
        STATE->generation == 0 || STATE->phase != UDEKS_CACHE_READY)
        return UDEKS_CACHE_INVALID;
    geometry_request(geometry);
    if (command(flow, UDEKS_CACHE_COMMAND_PASTE) != 0x83u)
        return UDEKS_CACHE_INVALID;
    STATE->phase = UDEKS_CACHE_PASTING;
    return UDEKS_CACHE_OK;
}

uint8_t udeks_cache_flow_step(struct udeks_cache_flow *flow,
    uint8_t handle, uint16_t generation)
{
    uint8_t result;
    if (handle == 0 || handle != STATE->handle || generation == 0 ||
        generation != STATE->generation ||
        (STATE->phase != UDEKS_CACHE_CAPTURING && STATE->phase != UDEKS_CACHE_PASTING))
        return UDEKS_CACHE_INVALID;
    result = command(flow, UDEKS_CACHE_COMMAND_STEP);
    /* Keep phase comparisons scalar. The equivalent variable bitmask form
     * crashes the reference cc65 optimizer; exact constants also reject a
     * missing or spurious WRITTEN bit without accepting other phases. */
    if (STATE->phase == UDEKS_CACHE_CAPTURING) {
        if (result == 0x81u) return UDEKS_CACHE_OK;
        if (result != 0x82u) goto failed;
    } else {
        if (result == 0xC3u) return UDEKS_CACHE_OK;
        if (result != 0xC2u) goto failed;
    }
    STATE->phase = UDEKS_CACHE_READY;
    return UDEKS_CACHE_OK;
failed:
    udeks_cache_flow_invalidate(flow); /* Caller must repaint on backend failure. */
    return UDEKS_CACHE_INVALID;
}

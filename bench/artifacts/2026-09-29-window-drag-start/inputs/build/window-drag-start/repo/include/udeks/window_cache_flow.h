/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private continuation prototype. Not production-linked or an application ABI. */
#ifndef UDEKS_WINDOW_CACHE_FLOW_H
#define UDEKS_WINDOW_CACHE_FLOW_H
#include "udeks/window_cache_state.h"

struct udeks_cache_flow {
    uint16_t generation;
    uint8_t handle, phase;
};

/* A cache owner is a WINDOW HANDLE, not an app/task id. Manager hooks must
 * invalidate before destruction/reuse, resize, restacking or pixel damage.
 * Capture requires explicit completion and an immutable source until READY;
 * paste requires a stable destination until READY. Those compositor locks
 * and delivery validation are not implemented by this policy prototype.
 * A continuation takes its original ticket, rejects stale tickets before
 * touching the shared request and invokes at most ONE bounded row command. */
uint8_t udeks_cache_flow_init(struct udeks_cache_flow *flow);
void udeks_cache_flow_invalidate(struct udeks_cache_flow *flow);
uint8_t udeks_cache_flow_capture(struct udeks_cache_flow *flow,
    uint8_t handle, const struct udeks_cache_geometry *geometry, uint8_t eligible);
uint8_t udeks_cache_flow_paste(struct udeks_cache_flow *flow,
    uint8_t handle, const struct udeks_cache_geometry *geometry);
uint8_t udeks_cache_flow_step(struct udeks_cache_flow *flow,
    uint8_t handle, uint16_t generation);
#endif

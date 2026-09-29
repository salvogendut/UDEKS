/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private manager-context adapter, NOT wired into production poll/lifecycle.
 * The caller asserts a quiescent serialized graphics lease with value 1.
 * Any other value (unadmitted, app-paint, shutdown, nested call) defers without
 * touching the packet, job, output, clip or pixels. No persistent lease byte
 * is hidden here: production admission/lease storage and callers are unbuilt.
 * INIT requires a fresh/quiesced lifetime; never re-init an outstanding job.
 */
#include "../window-repaint-bank/packet.h"
#define REPAINT_FRONTEND_DEFERRED 7u
extern unsigned char private_repaint_policy_call(void);
static unsigned char repaint_frontend_allowed(unsigned char lease)
{
    return lease == 1u && cache_accept_state == 0x80u &&
        (cache_phase == UDEKS_CACHE_EMPTY || cache_phase == UDEKS_CACHE_READY) &&
        udeks_vic_graphics_is_active();
}

/* Validated manager scene changes must fence BEFORE table/content edits.
 * If this defers, the caller must defer its edit too (or cancel the conflicting
 * cache lease first). ABORT is whole-surface teardown, not per-window close.
 * REQUEST queues pending damage without revoking the current receipt.
 */
unsigned char repaint_frontend_control(unsigned char op,
    const struct udeks_repaint_rect *damage, unsigned char lease)
{
    if (op > REPAINT_ABORT || ((op == REPAINT_REQUEST || op == REPAINT_CHANGED) && !damage))
        return UDEKS_REPAINT_INVALID;
    if (!repaint_frontend_allowed(lease)) return REPAINT_FRONTEND_DEFERRED;
    if (op == REPAINT_REQUEST || op == REPAINT_CHANGED) packet.damage = *damage;
    packet.op = op;
    return private_repaint_policy_call();
}

/* One manager-owned step maximum; never drains a whole job or calls a legacy
 * painter/cache provider. Caller output MUST be a local kernel-owned work copy,
 * not common packet/gateway scratch. CLIENT returns BACKEND_REQUIRED with its
 * receipt unacknowledged, for a future explicitly bounded provider contract.
 */
unsigned char repaint_frontend_poll(unsigned char lease,
    struct udeks_repaint_lane_work *output)
{
    register const struct udeks_window *window;
    register struct udeks_repaint_window *view;
    register unsigned char index, count;
    unsigned char status;

    if (!output) return UDEKS_REPAINT_INVALID;
    if (!repaint_frontend_allowed(lease) || dragging_handle != UDEKS_WINDOW_NONE)
        return REPAINT_FRONTEND_DEFERRED;
    count = 0;
    view = packet.windows;
    for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
        window = &windows[index];
        if (!window->z || !(window->flags & UDEKS_WINDOW_FLAG_VISIBLE)) continue;
        /* Trusted table, but do not publish wrapping geometry to bank policy. */
        if (window->z > UDEKS_WINDOW_MAX || window->width < 16u || window->width > UDEKS_VIC_WIDTH ||
            window->height <= UDEKS_WINDOW_TITLE_HEIGHT + 4u ||
            window->height > UDEKS_VIC_HEIGHT ||
            window->x > UDEKS_VIC_WIDTH - window->width ||
            window->y > UDEKS_VIC_HEIGHT - window->height)
            return UDEKS_REPAINT_INVALID;
        view->bounds.left = window->x;
        view->bounds.right = window->x + window->width;
        view->bounds.top = window->y;
        view->bounds.bottom = window->y + window->height;
        view->handle = index + 1u;
        view->rank = window->z;
        view->flags = UDEKS_REPAINT_VISIBLE; /* No unqualified retained provider. */
        ++view;
        ++count;
    }
    packet.count = count;
    packet.op = REPAINT_PEEK;
    status = private_repaint_policy_call();
    if (status != UDEKS_REPAINT_OK) return status;
    *output = packet.work; /* Before any pixel/gateway may reuse that packet. */
    return lane_raster_step(output);
}

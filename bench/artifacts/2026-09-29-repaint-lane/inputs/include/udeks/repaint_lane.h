/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private single-surface prototype, NOT a public UAPP ABI or resident service. */
#ifndef UDEKS_REPAINT_LANE_H
#define UDEKS_REPAINT_LANE_H
#include "udeks/window_repaint.h"

/* The one epoch fences both scene changes and job replacement. The manager
 * MUST invalidate before changing its validated table/cache/content. There is
 * no independent caller-supplied revision here and no untrusted scene parser.
 * current replaces the old six-byte manager damage box; the rest costs twelve
 * bytes. No overlap with drag fields, pointers, cache scratch, stack or guards.
 */
#define UDEKS_LANE_PENDING 8u
struct udeks_repaint_lane {
    struct udeks_repaint_rect current, pending;
    uint16_t epoch, cursor;
    uint8_t state, selector; /* phase: bits 0-2; rank/handle: selector bits 3-5/0-2 */
};
struct udeks_repaint_lane_ticket {
    uint16_t epoch, cursor;
    uint8_t phase, selector;
};
struct udeks_repaint_lane_work {
    struct udeks_repaint_lane_ticket ticket;
    struct udeks_repaint_rect clip;
};
/* Explicit service-owned storage for the sizing spike. No normal link uses
 * it. Integration must replace (not retain) the old damage globals and compact
 * the window table first. Target HIGHBSS cost is 18, not zero/hidden state. */
extern struct udeks_repaint_lane udeks_repaint_lane;

/* Fresh/quiesced lifetime only; all old work must be retired before init. */
void udeks_lane_init(void);
uint8_t udeks_lane_request(const struct udeks_repaint_rect *damage);
uint8_t udeks_lane_changed(const struct udeks_repaint_rect *damage);
uint8_t udeks_lane_abort(void); /* whole surface shutdown only */
/* Trusted manager views, validated geometry/unique handles/ranks, count <= 4.
 * No view/callback/title/cache pointer is retained between calls. */
uint8_t udeks_lane_peek(const struct udeks_repaint_window *windows, uint8_t count,
    struct udeks_repaint_lane_work *work);
uint8_t udeks_lane_validate(const struct udeks_repaint_lane_ticket *ticket);
/* One cooperative poll: validate BEFORE pixels, do not yield until the bounded
 * step ends, reset clip, then ack. Pending-only requests do not revoke active
 * work; changed/abort do. MORE has a 16-bit replay-resistant progress cursor. */
uint8_t udeks_lane_ack(const struct udeks_repaint_lane_ticket *ticket, uint8_t result);
#endif

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private window-service policy prototype; not UAPP or production-linked. */
#ifndef UDEKS_WINDOW_REPAINT_H
#define UDEKS_WINDOW_REPAINT_H
#include <stdint.h>

#define UDEKS_REPAINT_OK         0u
#define UDEKS_REPAINT_IDLE       1u
#define UDEKS_REPAINT_INVALID    2u
#define UDEKS_REPAINT_STALE      3u
#define UDEKS_REPAINT_EXHAUSTED  4u
#define UDEKS_REPAINT_YIELD      5u /* No record this poll; job still active. */
#define UDEKS_REPAINT_DONE       0u
#define UDEKS_REPAINT_MORE       1u

#define UDEKS_REPAINT_CLEAR      1u
#define UDEKS_REPAINT_SELECT     2u /* Internal, never a work record. */
#define UDEKS_REPAINT_CHROME     3u /* Opaque window background + decorations. */
#define UDEKS_REPAINT_CLIENT     4u
#define UDEKS_REPAINT_RESTORE    5u /* Retained whole-window pixels, clipped. */
#define UDEKS_REPAINT_COMMIT     6u
#define UDEKS_REPAINT_FAILED     7u
#define UDEKS_REPAINT_VISIBLE    1u
#define UDEKS_REPAINT_RETAINED   2u
#define UDEKS_REPAINT_CLEAR_ROWS 4u

/* Half-open rectangles: 0 <= left < right <= 320, top < bottom <= 200. */
struct udeks_repaint_rect {
    uint16_t left, right;
    uint8_t top, bottom;
};
struct udeks_repaint_window {
    struct udeks_repaint_rect bounds;
    uint8_t handle, rank, flags;
};
struct udeks_repaint_job {
    struct udeks_repaint_rect current, pending;
    uint16_t generation, revision, cursor;
    uint8_t phase, rank, handle, pending_valid;
};
struct udeks_repaint_ticket {
    uint16_t generation, revision, cursor;
    uint8_t phase, rank, handle;
};
struct udeks_repaint_work {
    struct udeks_repaint_ticket ticket;
    struct udeks_repaint_rect clip;
};

/* Init is ONLY for a fresh/quiesced lifetime with all old tickets retired.
 * Generations/cursors never wrap: exhaustion closes the job, not an ABA alias.
 * The caller owns scene/cache locks and resolves handles immediately before
 * rendering. No callback, app address or cache pointer is stored here. */
uint8_t udeks_repaint_init(struct udeks_repaint_job *job, uint16_t revision);
uint8_t udeks_repaint_request(struct udeks_repaint_job *job,
    const struct udeks_repaint_rect *damage);
/* Before changing geometry/rank/visibility/lifetime/content/cache eligibility:
 * withdraw the old ticket, union active + pending + old/new damage, then allow
 * the new scene to render. Do not use request alone for structural changes. */
uint8_t udeks_repaint_scene_changed(struct udeks_repaint_job *job,
    uint16_t revision, const struct udeks_repaint_rect *damage);
/* Discard work only when the whole graphics surface is retired, e.g. shutdown.
 * Closing one window instead uses scene_changed and repairs exposed content. */
uint8_t udeks_repaint_abort(struct udeks_repaint_job *job);
uint8_t udeks_repaint_peek(struct udeks_repaint_job *job, uint16_t revision,
    const struct udeks_repaint_window *windows, uint8_t count,
    struct udeks_repaint_work *work);
/* Validate again immediately before any pixels are changed. The cooperative
 * driver must not yield between validation and its bounded raster operation.
 * ack validates again; a rejected/stale ack cannot advance the continuation. */
uint8_t udeks_repaint_validate(const struct udeks_repaint_job *job,
    uint16_t revision, const struct udeks_repaint_ticket *ticket);
uint8_t udeks_repaint_ack(struct udeks_repaint_job *job, uint16_t revision,
    const struct udeks_repaint_ticket *ticket, uint8_t result);
#endif

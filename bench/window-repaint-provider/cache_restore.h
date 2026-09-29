/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private full-window retained provider; not a window/UAPP ABI. */
#ifndef UDEKS_PRIVATE_REPAINT_CACHE_RESTORE_H
#define UDEKS_PRIVATE_REPAINT_CACHE_RESTORE_H
#include "udeks/repaint_lane.h"

#define REPAINT_RESTORE_DEFERRED 7u
#define REPAINT_RESTORE_REPAIR_QUEUED 8u
#define REPAINT_RESTORE_UNRECOVERABLE 9u

/* These fixed entries run with the caller's synchronous CACHE admission.
 * work/window must be local snapshots of manager-owned state. Every cache
 * mutation, including those between polls, must use this admission and
 * invalidate the lane epoch before changing retained image identity.
 * image_valid checks manager content generation against the cache lease in
 * both READY and PASTING; it returns CACHE_OK, CACHE_BUSY (defer), or
 * CACHE_INVALID (repair), and must not issue the READY-only cache command.
 * begin_full is atomic on rejection. repair, under the already-held admission,
 * invalidates retained eligibility and queues the whole window as changed;
 * it must not try to acquire admission recursively or call an app painter. */
unsigned char repaint_restore_validate(const struct udeks_repaint_lane_ticket *ticket);
unsigned char repaint_restore_ack(const struct udeks_repaint_lane_ticket *ticket,
                                  unsigned char completion);
unsigned char repaint_restore_image_valid(unsigned char handle);
unsigned char repaint_restore_phase(void);
unsigned char repaint_restore_owner(void);
unsigned char repaint_restore_row(void);
unsigned char repaint_restore_begin_full(unsigned char handle);
unsigned char repaint_restore_step_row(void);
void repaint_restore_commit(void);
unsigned char repaint_restore_repair(unsigned char handle,
                                    const struct udeks_repaint_rect *bounds);

unsigned char repaint_restore_step(const struct udeks_repaint_lane_work *work,
                                  const struct udeks_repaint_window *window);
#endif

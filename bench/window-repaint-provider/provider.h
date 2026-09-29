/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private host/compile-only client-step contract. Not a UAPP entry point. */
#ifndef UDEKS_PRIVATE_REPAINT_PROVIDER_H
#define UDEKS_PRIVATE_REPAINT_PROVIDER_H
#include "udeks/repaint_lane.h"

#define REPAINT_PROVIDER_DEFER 7u /* distinct from raster BACKEND_REQUIRED=6 */

/* Fixed private dispatcher imports avoid a per-call callback table. Each
 * returns before the next begins. validate/ack may cross the banked policy
 * gateway, but draw_row must not run inside that gateway. ready is a pure
 * admission check and may decline before pixels. draw_row must do bounded
 * work on exactly one scanline, without yielding, scene edits, or retained
 * pointers. Actual UDEX app bridging and each app's step bound remain to be
 * qualified; the current void xclock/xwave painters do not meet this ABI. */
unsigned char repaint_client_validate(const struct udeks_repaint_lane_ticket *ticket);
unsigned char repaint_client_ack(const struct udeks_repaint_lane_ticket *ticket,
                                 unsigned char result);
unsigned char repaint_client_ready(unsigned char handle, unsigned char row);
void repaint_client_set_clip(unsigned int left, unsigned char top,
                             unsigned int width, unsigned char height);
void repaint_client_draw_row(unsigned char handle, unsigned char row);
void repaint_client_reset_clip(void);

unsigned char repaint_client_step(const struct udeks_repaint_lane_work *work,
    const struct udeks_repaint_window *window);
#endif

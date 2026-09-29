/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private bounded manager backend. Register/byte specialization preserves the
 * old validation rules; it does not trust a forged clip/page or stale receipt.
 * No persistent scratch, callbacks or hidden provider work in this function.
 */
#include "udeks/repaint_lane.h"
#include "udeks/memory.h"
#define UDEKS_LANE_BACKEND_REQUIRED 6u
#ifndef REPAINT_DIRTY_MAP
#define REPAINT_DIRTY_MAP ((unsigned char *)UDEKS_VIC_DIRTY_MAP_BASE)
#endif
extern void udeks_vic_bitmap_commit_page(unsigned char page);
extern unsigned char repaint_receipt_validate(const struct udeks_repaint_lane_ticket *ticket);
extern unsigned char repaint_receipt_ack(const struct udeks_repaint_lane_ticket *ticket, unsigned char result);
unsigned char lane_raster_step(register const struct udeks_repaint_lane_work *work)
{
    register const struct udeks_window *window;
    register unsigned char row, more = 0;
    unsigned char status;

    if (!work) return UDEKS_REPAINT_INVALID;
    status = repaint_receipt_validate(&work->ticket);
    if (status != 0) return status;
    if (work->ticket.phase == UDEKS_REPAINT_COMMIT) {
        if (work->ticket.cursor >= UDEKS_VIC_BITMAP_PAGES) return UDEKS_REPAINT_INVALID;
        status = (unsigned char)work->ticket.cursor;
        if (REPAINT_DIRTY_MAP[status]) {
            udeks_vic_bitmap_commit_page(status);
            REPAINT_DIRTY_MAP[status] = 0;
        }
        more = status != UDEKS_VIC_BITMAP_PAGES - 1u;
    } else {
        if (work->ticket.phase != UDEKS_REPAINT_CLEAR && work->ticket.phase != UDEKS_REPAINT_CHROME)
            return UDEKS_LANE_BACKEND_REQUIRED;
        if (work->clip.left >= work->clip.right || work->clip.right > UDEKS_VIC_WIDTH ||
            work->clip.top >= work->clip.bottom || work->clip.bottom > UDEKS_VIC_HEIGHT)
            return UDEKS_REPAINT_INVALID;
        if (work->ticket.phase == UDEKS_REPAINT_CLEAR) {
            if (work->clip.bottom - work->clip.top > UDEKS_REPAINT_CLEAR_ROWS)
                return UDEKS_REPAINT_INVALID;
            window = 0;
            row = 0;
        } else {
            window = window_by_handle(work->ticket.selector & 7u);
            if (!window || window->z != work->ticket.selector >> 3 ||
                work->clip.left < window->x || work->clip.right > window->x + window->width ||
                work->clip.top < window->y || work->clip.bottom > window->y + window->height ||
                work->ticket.cursor >= work->clip.bottom - work->clip.top)
                return UDEKS_REPAINT_STALE;
            /* The validated bottom is <=200, and cursor < clip height, so
             * this coordinate can be narrowed to a byte without wrapping. */
            row = work->clip.top + work->ticket.cursor;
            more = row + 1u < work->clip.bottom;
        }
        udeks_vic_bitmap_set_clip(work->clip.left, work->clip.top,
            work->clip.right - work->clip.left, work->clip.bottom - work->clip.top);
        if (!window)
            udeks_vic_bitmap_fill(work->clip.left, work->clip.top,
                work->clip.right - work->clip.left, work->clip.bottom - work->clip.top,
                UDEKS_VIC_COLOR_YELLOW);
        else draw_chrome_row(window, row - window->y);
    }
    udeks_vic_bitmap_reset_clip();
    return repaint_receipt_ack(&work->ticket, more);
}

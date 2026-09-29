/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private prototype adapter: manager-owned stages only. The legacy client
 * callback and retained-image lease are NOT executed here or called bounded.
 * Includes chrome.inc first, in a translation unit with the real manager.
 */
#include "udeks/repaint_lane.h"
#include "udeks/memory.h"
#define UDEKS_LANE_BACKEND_REQUIRED 6u
#ifndef REPAINT_DIRTY_MAP
#define REPAINT_DIRTY_MAP ((unsigned char *)UDEKS_VIC_DIRTY_MAP_BASE)
#endif
extern void udeks_vic_bitmap_commit_page(unsigned char page);

/* Export only to retain this private bench entry in the cc65 object. It has
 * no UAPP jump-table entry and is not a production service/API. */
unsigned char lane_raster_step(const struct udeks_repaint_lane_work *work)
{
    register const struct udeks_window *window;
    unsigned char status, more = 0;
    unsigned int row;

    if (!work) return UDEKS_REPAINT_INVALID;
    status = udeks_lane_validate(&work->ticket);
    if (status != 0) return status; /* Before clip/workspace/pixels. */
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
            row = work->clip.top + work->ticket.cursor;
            more = row + 1u < work->clip.bottom;
        }
        udeks_vic_bitmap_set_clip(work->clip.left, work->clip.top,
            work->clip.right - work->clip.left, work->clip.bottom - work->clip.top);
        if (!window)
            udeks_vic_bitmap_fill(work->clip.left, work->clip.top,
                work->clip.right - work->clip.left, work->clip.bottom - work->clip.top,
                UDEKS_VIC_COLOR_YELLOW);
        else draw_chrome_row(window, (unsigned char)(row - window->y));
    }
    udeks_vic_bitmap_reset_clip();
    return udeks_lane_ack(&work->ticket, more);
}

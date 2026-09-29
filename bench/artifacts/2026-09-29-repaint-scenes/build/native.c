/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/pointer.h"
#include "udeks/vic_graphics.h"
#include "udeks/window.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))

#define POINTER_X_BIAS       12u
#define POINTER_Y_BIAS       40u
#define ACTION_BUTTONS       0x05u
#define DRAG_MOVE            1u
#define DRAG_RESIZE          2u
#define MINIMUM_WIDTH        48u
#define MINIMUM_HEIGHT       48u
#define IMAGE_COMPLETE       0x80u /* private; never accepted from create flags */

struct udeks_window {
    unsigned char flags;
    unsigned int x;
    unsigned char y;
    unsigned int width;
    unsigned char height;
    unsigned char z;
    const unsigned char *title;
    udeks_window_paint_fn paint;
    udeks_window_close_fn close;
};

#pragma bss-name(push, "HIGHBSS")
static struct udeks_window windows[UDEKS_WINDOW_MAX];
static unsigned char active_count;
static unsigned char focused_handle;
static unsigned char dragging_handle;
static unsigned char previous_buttons;
static unsigned int drag_pointer_x;
static unsigned char drag_pointer_y;
static unsigned int drag_x;
static unsigned char drag_y;
static unsigned int drag_width;
static unsigned char drag_height;
static unsigned char drag_mode;
static unsigned int damage_left;
static unsigned char damage_top;
static unsigned int damage_right;
static unsigned char damage_bottom;
#pragma bss-name(pop)

static const unsigned char title_glyphs[26][5] = {
    {2, 5, 7, 5, 5}, {6, 5, 6, 5, 6}, {3, 4, 4, 4, 3},
    {6, 5, 5, 5, 6}, {7, 4, 6, 4, 7}, {7, 4, 6, 4, 4},
    {3, 4, 5, 5, 3}, {5, 5, 7, 5, 5}, {7, 2, 2, 2, 7},
    {1, 1, 1, 5, 2}, {5, 5, 6, 5, 5}, {4, 4, 4, 4, 7},
    {5, 7, 7, 5, 5}, {5, 7, 7, 7, 5}, {2, 5, 5, 5, 2},
    {6, 5, 6, 4, 4}, {2, 5, 5, 3, 1}, {6, 5, 6, 5, 5},
    {3, 4, 2, 1, 6}, {7, 2, 2, 2, 2}, {5, 5, 5, 5, 7},
    {5, 5, 5, 5, 2}, {5, 5, 7, 7, 5}, {5, 5, 2, 5, 5},
    {5, 5, 2, 2, 2}, {7, 1, 2, 4, 7}
};


static struct udeks_window *window_by_handle(unsigned char handle)
{
    if (handle == UDEKS_WINDOW_NONE || handle > UDEKS_WINDOW_MAX ||
        windows[handle - 1u].z == 0) {
        return 0;
    }
    return &windows[handle - 1u];
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private measured replacement; not linked by normal UDEKS. These twelve
 * HIGHBSS bytes belong to one serialized manager drawing step. No callbacks,
 * polls or IRQ drawing inside it; never overlay drag fields or cache guards.
 * Title/window pointers stay automatic and are not retained between steps.
 */
#pragma bss-name(push, "HIGHBSS")
static unsigned int chrome_x, chrome_width, chrome_right;
static unsigned char chrome_y, chrome_offset, chrome_character, chrome_bits, chrome_column, chrome_color;
#pragma bss-name(pop)
static void chrome_pixel(unsigned int at)
{
    udeks_vic_bitmap_pixel(at, chrome_y, UDEKS_VIC_COLOR_BLACK);
}
static void chrome_span(unsigned int at, unsigned int width)
{
    udeks_vic_bitmap_fill(at, chrome_y, width, 1, chrome_color);
}
static void draw_chrome_row(register const struct udeks_window *window,
    unsigned char row)
{
    const unsigned char *text;

    chrome_x = window->x;
    chrome_y = window->y + row;
    chrome_width = window->width;
    chrome_right = chrome_x + chrome_width - 1u;
    chrome_color = row == 0 || row == window->height - 1u ? UDEKS_VIC_COLOR_BLACK : UDEKS_VIC_COLOR_YELLOW;
    chrome_span(chrome_x, chrome_width);
    if (chrome_color != UDEKS_VIC_COLOR_BLACK) {
        chrome_pixel(chrome_x);
        chrome_pixel(chrome_right);
    }
    chrome_color = UDEKS_VIC_COLOR_BLACK;
    if (row >= 2u && row <= window->height - 3u) {
        if (row == 2u || row == window->height - 3u || row == UDEKS_WINDOW_TITLE_HEIGHT)
            chrome_span(chrome_x + 2u, chrome_width - 4u);
        else {
            chrome_pixel(chrome_x + 2u);
            chrome_pixel(chrome_right - 2u);
        }
    }
    if ((window->flags & UDEKS_WINDOW_FLAG_CLOSABLE) && row >= 3u && row <= 10u) {
        chrome_x = chrome_right - 11u;
        if (row == 3u || row == 10u)
            chrome_span(chrome_x, 8);
        else {
            chrome_pixel(chrome_x);
            chrome_pixel(chrome_x + 7u);
        }
        if (row >= 5u && row <= 8u) {
            chrome_pixel(chrome_x + row - 3u);
            chrome_pixel(chrome_x + 10u - row);
        }
    }
    if (window->flags & UDEKS_WINDOW_FLAG_RESIZABLE) {
        /* Valid height/row give -4..195. Converting negative values to a
         * byte gives 252..255, outside both stroke ranges. */
        chrome_offset = window->height - 5u - row;
        if (chrome_offset <= 6u)
            chrome_pixel(chrome_right - 10u + chrome_offset);
        if (chrome_offset <= 3u)
            chrome_pixel(chrome_right - 7u + chrome_offset);
    }
    if (row < 4u || row > 8u) return;
    text = window->title;
    chrome_x = window->x + 4u;
    chrome_right -= 13u;
    while (text && *text && chrome_x + 3u <= chrome_right) {
        chrome_character = *text++;
        if (chrome_character >= 'a' && chrome_character <= 'z') chrome_character -= 'a' - 'A';
        if (chrome_character >= 'A' && chrome_character <= 'Z') {
            chrome_bits = title_glyphs[chrome_character - 'A'][row - 4u];
            for (chrome_column = 0; chrome_column < 3u; ++chrome_column)
                if (chrome_bits & (4u >> chrome_column))
                    chrome_pixel(chrome_x + chrome_column);
        }
        chrome_x += 4u;
    }
}

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



#include "udeks/window_cache_state.h"
volatile unsigned char cache_accept_state=0x80,cache_phase;
unsigned char udeks_vic_graphics_is_active(void) { return 1; }
/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private manager-context adapter, NOT wired into production poll/lifecycle.
 * The caller asserts a quiescent serialized graphics lease with value 1.
 * Any other value (unadmitted, app-paint, shutdown, nested call) defers without
 * touching the packet, job, output, clip or pixels. No persistent lease byte
 * is hidden here: production admission/lease storage and callers are unbuilt.
 * INIT requires a fresh/quiesced lifetime; never re-init an outstanding job.
 */
#include "../window-repaint-scenes/packet.h"
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
/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Exactly the value-only prefix, never a whole window or its trailing pointers.
 * Host assertions and a compiler-emitted target layout sidecar gate the copy. */
#include <string.h>
#ifndef __CC65__
typedef char prefix_flags[(offsetof(struct udeks_window,flags)==0)?1:-1];
typedef char prefix_x[(offsetof(struct udeks_window,x)==1)?1:-1];
typedef char prefix_y[(offsetof(struct udeks_window,y)==3)?1:-1];
typedef char prefix_width[(offsetof(struct udeks_window,width)==4)?1:-1];
typedef char prefix_height[(offsetof(struct udeks_window,height)==6)?1:-1];
typedef char prefix_rank[(offsetof(struct udeks_window,z)==7)?1:-1];
typedef char prefix_end[(offsetof(struct udeks_window,title)==8)?1:-1];
#endif
unsigned char repaint_frontend_poll(unsigned char lease,
    struct udeks_repaint_lane_work *output)
{
    register const struct udeks_window *window;
    register struct repaint_scene *scene;
    unsigned char remaining, status;
    REPAINT_PACKET_CHECK();
    if (!output) return UDEKS_REPAINT_INVALID;
    if (!repaint_frontend_allowed(lease) || dragging_handle!=UDEKS_WINDOW_NONE)
        return REPAINT_FRONTEND_DEFERRED;
    window=windows;scene=packet.scenes;
    remaining=4;
    do { memcpy(scene,window,8);++window;++scene; } while(--remaining);
    packet.count=REPAINT_SCENE_FORMAT;
    packet.reserved[0]=packet.reserved[1]=packet.reserved[2]=packet.reserved[3]=0;
    packet.op=REPAINT_PEEK;
    status=private_repaint_policy_call();
    if (status!=UDEKS_REPAINT_OK) return status;
    *output=packet.work;
    return lane_raster_step(output);
}

#include "probe.inc"

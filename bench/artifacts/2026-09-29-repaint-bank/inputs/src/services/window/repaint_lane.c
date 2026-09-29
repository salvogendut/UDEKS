/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private compile/host spike; no pixels, callbacks or bank switches here. */
#include <string.h>
#include "udeks/repaint_lane.h"

#pragma bss-name(push, "HIGHBSS")
struct udeks_repaint_lane udeks_repaint_lane;
#pragma bss-name(pop)
#define lane udeks_repaint_lane
#define PHASE (lane.state & 7u)
#define RANK (lane.selector >> 3)
#define HANDLE (lane.selector & 7u)

static uint8_t live(void)
{
    if (lane.state & 0xF0u) return UDEKS_REPAINT_INVALID;
    return lane.epoch == 0 || PHASE == UDEKS_REPAINT_FAILED ?
        UDEKS_REPAINT_EXHAUSTED : UDEKS_REPAINT_OK;
}
static void phase(uint8_t next)
{
    lane.state = (lane.state & UDEKS_LANE_PENDING) | next;
}
static uint8_t advance(void)
{
    if (lane.epoch == 0xFFFFu) {
        lane.epoch = lane.cursor = 0;
        lane.selector &= 0x38u;
        phase(UDEKS_REPAINT_FAILED);
        return UDEKS_REPAINT_EXHAUSTED;
    }
    ++lane.epoch;
    return UDEKS_REPAINT_OK;
}
static uint8_t valid(const struct udeks_repaint_rect *r)
{
    return r != 0 && r->left < r->right && r->right <= 320u &&
        r->top < r->bottom && r->bottom <= 200u;
}
static void unite(struct udeks_repaint_rect *r, const struct udeks_repaint_rect *a)
{
    if (a->left < r->left) r->left = a->left;
    if (a->right > r->right) r->right = a->right;
    if (a->top < r->top) r->top = a->top;
    if (a->bottom > r->bottom) r->bottom = a->bottom;
}
static uint8_t intersect(struct udeks_repaint_rect *r, const struct udeks_repaint_rect *a)
{
    r->left = a->left > lane.current.left ? a->left : lane.current.left;
    r->right = a->right < lane.current.right ? a->right : lane.current.right;
    r->top = a->top > lane.current.top ? a->top : lane.current.top;
    r->bottom = a->bottom < lane.current.bottom ? a->bottom : lane.current.bottom;
    return r->left < r->right && r->top < r->bottom;
}
void udeks_lane_init(void)
{
    memset(&lane, 0, sizeof(lane));
    lane.epoch = 1;
}
uint8_t udeks_lane_request(const struct udeks_repaint_rect *damage)
{
    uint8_t result = live();
    if (result != 0) return result;
    if (!valid(damage)) return UDEKS_REPAINT_INVALID;
    if (lane.state & UDEKS_LANE_PENDING) unite(&lane.pending, damage);
    else lane.pending = *damage;
    lane.state |= UDEKS_LANE_PENDING;
    return UDEKS_REPAINT_OK;
}
uint8_t udeks_lane_changed(const struct udeks_repaint_rect *damage)
{
    struct udeks_repaint_rect merged;
    uint8_t result = live();
    if (result != 0) return result;
    if (!valid(damage)) return UDEKS_REPAINT_INVALID;
    merged = *damage;
    if (PHASE != 0) unite(&merged, &lane.current);
    if (lane.state & UDEKS_LANE_PENDING) unite(&merged, &lane.pending);
    result = advance();
    lane.pending = merged;
    lane.state |= UDEKS_LANE_PENDING;
    if (result != 0) return result;
    phase(0);
    lane.selector = 0;
    lane.cursor = 0;
    return UDEKS_REPAINT_OK;
}
uint8_t udeks_lane_abort(void)
{
    uint16_t epoch;
    uint8_t result = live();
    if (result != 0) return result;
    result = advance();
    if (result != 0) return result;
    epoch = lane.epoch;
    memset(&lane, 0, sizeof(lane));
    lane.epoch = epoch;
    return UDEKS_REPAINT_OK;
}
uint8_t udeks_lane_peek(const struct udeks_repaint_window *windows, uint8_t count,
    struct udeks_repaint_lane_work *work)
{
    const struct udeks_repaint_window *w;
    struct udeks_repaint_rect clip, bounds;
    uint8_t i, selected, result = live();
    if (result != 0) return result;
    if (!work || count > 4u || (count && !windows)) return UDEKS_REPAINT_INVALID;
    if (PHASE == 0) {
        if (!(lane.state & UDEKS_LANE_PENDING)) return UDEKS_REPAINT_IDLE;
        result = advance();
        if (result != 0) return result;
        lane.current = lane.pending;
        lane.state = UDEKS_REPAINT_CLEAR;
        lane.selector = 0;
        lane.cursor = lane.current.top;
    }
    if (PHASE == UDEKS_REPAINT_CLEAR) {
        clip = lane.current;
        clip.top = (uint8_t)lane.cursor;
        clip.bottom = clip.top + UDEKS_REPAINT_CLEAR_ROWS;
        if (clip.bottom > lane.current.bottom) clip.bottom = lane.current.bottom;
    } else {
        if (PHASE == UDEKS_REPAINT_SELECT) {
            selected = count;
            for (i = 0; i < count; ++i) {
                w = &windows[i];
                if (w->rank > RANK && (w->flags & UDEKS_REPAINT_VISIBLE) &&
                    (selected == count || w->rank < windows[selected].rank) &&
                    intersect(&clip, &w->bounds)) selected = i;
            }
            lane.cursor = 0;
            if (selected == count) {
                lane.selector &= 0x38u;
                phase(UDEKS_REPAINT_COMMIT);
            } else {
                w = &windows[selected];
                lane.selector = (w->rank << 3) | w->handle;
                phase(w->flags & UDEKS_REPAINT_RETAINED ? UDEKS_REPAINT_RESTORE : UDEKS_REPAINT_CHROME);
            }
        }
        if (PHASE == UDEKS_REPAINT_COMMIT) clip = lane.current;
        else {
            for (i = 0; i < count && windows[i].handle != HANDLE; ++i) {}
            if (i == count) return UDEKS_REPAINT_STALE;
            bounds = windows[i].bounds;
            if (PHASE == UDEKS_REPAINT_CLIENT) {
                bounds.left += 3u;
                bounds.right -= 3u;
                bounds.top += 14u;
                bounds.bottom -= 3u;
                if (!intersect(&clip, &bounds)) {
                    phase(UDEKS_REPAINT_SELECT);
                    lane.selector &= 0x38u;
                    lane.cursor = 0;
                    return UDEKS_REPAINT_YIELD;
                }
            } else if (!intersect(&clip, &bounds)) return UDEKS_REPAINT_STALE;
        }
    }
    work->clip = clip;
    work->ticket.epoch = lane.epoch;
    work->ticket.cursor = lane.cursor;
    work->ticket.phase = PHASE;
    work->ticket.selector = lane.selector;
    return UDEKS_REPAINT_OK;
}
uint8_t udeks_lane_validate(const struct udeks_repaint_lane_ticket *ticket)
{
    uint8_t result = live();
    if (result != 0) return result;
    if (!ticket) return UDEKS_REPAINT_INVALID;
    if (ticket->epoch != lane.epoch || ticket->cursor != lane.cursor ||
        ticket->phase != PHASE || ticket->selector != lane.selector ||
        PHASE == 0 || PHASE == UDEKS_REPAINT_SELECT) return UDEKS_REPAINT_STALE;
    return UDEKS_REPAINT_OK;
}
uint8_t udeks_lane_ack(const struct udeks_repaint_lane_ticket *ticket, uint8_t result)
{
    uint8_t status = udeks_lane_validate(ticket);
    if (status != 0) return status;
    if (result > UDEKS_REPAINT_MORE || (PHASE == UDEKS_REPAINT_CLEAR && result != 0))
        return UDEKS_REPAINT_INVALID;
    if (PHASE == UDEKS_REPAINT_CLEAR) {
        lane.cursor += UDEKS_REPAINT_CLEAR_ROWS;
        if (lane.cursor >= lane.current.bottom) {
            phase(UDEKS_REPAINT_SELECT);
            lane.cursor = 0;
        }
    } else if (result == UDEKS_REPAINT_MORE) {
        if (lane.cursor == 0xFFFFu) {
            lane.epoch = 0;
            lane.selector &= 0x38u;
            phase(UDEKS_REPAINT_FAILED);
            return UDEKS_REPAINT_EXHAUSTED;
        }
        ++lane.cursor;
    } else {
        lane.cursor = 0;
        if (PHASE == UDEKS_REPAINT_CHROME) phase(UDEKS_REPAINT_CLIENT);
        else {
            lane.selector &= 0x38u;
            phase(PHASE == UDEKS_REPAINT_COMMIT ? 0 : UDEKS_REPAINT_SELECT);
        }
    }
    return UDEKS_REPAINT_OK;
}

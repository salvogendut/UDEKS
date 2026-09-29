/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Host/budget seam only. No drawing, callbacks, MMU changes or hidden state. */
#include <string.h>
#include "udeks/window_repaint.h"

static uint8_t valid_rect(const struct udeks_repaint_rect *r)
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

static uint8_t intersect(struct udeks_repaint_rect *r,
    const struct udeks_repaint_rect *a, const struct udeks_repaint_rect *b)
{
    r->left = a->left > b->left ? a->left : b->left;
    r->right = a->right < b->right ? a->right : b->right;
    r->top = a->top > b->top ? a->top : b->top;
    r->bottom = a->bottom < b->bottom ? a->bottom : b->bottom;
    return r->left < r->right && r->top < r->bottom;
}

static uint8_t live(const struct udeks_repaint_job *job)
{
    if (job == 0 || job->revision == 0) return UDEKS_REPAINT_INVALID;
    if (job->phase > UDEKS_REPAINT_FAILED) return UDEKS_REPAINT_INVALID;
    if (job->generation == 0 || job->phase == UDEKS_REPAINT_FAILED)
        return UDEKS_REPAINT_EXHAUSTED;
    return UDEKS_REPAINT_OK;
}

static uint8_t next_generation(struct udeks_repaint_job *job)
{
    if (job->generation == 0xFFFFu) {
        job->generation = 0;
        job->phase = UDEKS_REPAINT_FAILED;
        job->handle = 0;
        job->cursor = 0;
        return UDEKS_REPAINT_EXHAUSTED;
    }
    ++job->generation;
    return UDEKS_REPAINT_OK;
}

uint8_t udeks_repaint_init(struct udeks_repaint_job *job, uint16_t revision)
{
    if (job == 0 || revision == 0) return UDEKS_REPAINT_INVALID;
    memset(job, 0, sizeof(*job));
    job->generation = 1;
    job->revision = revision;
    return UDEKS_REPAINT_OK;
}

uint8_t udeks_repaint_request(struct udeks_repaint_job *job,
    const struct udeks_repaint_rect *damage)
{
    uint8_t status = live(job);
    if (status != UDEKS_REPAINT_OK) return status;
    if (!valid_rect(damage)) return UDEKS_REPAINT_INVALID;
    if (job->pending_valid) unite(&job->pending, damage);
    else job->pending = *damage;
    job->pending_valid = 1;
    return UDEKS_REPAINT_OK;
}

uint8_t udeks_repaint_scene_changed(struct udeks_repaint_job *job,
    uint16_t revision, const struct udeks_repaint_rect *damage)
{
    struct udeks_repaint_rect merged;
    uint8_t status = live(job);
    if (status != UDEKS_REPAINT_OK) return status;
    if (!valid_rect(damage) || revision == 0 || revision == job->revision)
        return UDEKS_REPAINT_INVALID;
    merged = *damage;
    if (job->phase != 0) unite(&merged, &job->current);
    if (job->pending_valid) unite(&merged, &job->pending);
    status = next_generation(job);
    job->pending = merged; /* Preserve repair extent even if lifetime closes. */
    job->pending_valid = 1;
    if (status != UDEKS_REPAINT_OK) return status;
    job->revision = revision;
    job->phase = 0;
    job->rank = job->handle = 0;
    job->cursor = 0;
    return UDEKS_REPAINT_OK;
}

uint8_t udeks_repaint_abort(struct udeks_repaint_job *job)
{
    uint16_t generation, revision;
    uint8_t status = live(job);
    if (status != UDEKS_REPAINT_OK) return status;
    status = next_generation(job);
    if (status != UDEKS_REPAINT_OK) return status;
    generation = job->generation;
    revision = job->revision;
    memset(job, 0, sizeof(*job));
    job->generation = generation;
    job->revision = revision;
    return UDEKS_REPAINT_OK;
}

static uint8_t valid_scene(const struct udeks_repaint_window *windows, uint8_t count)
{
    uint8_t i, j;
    const struct udeks_repaint_window *w;
    if (count > 4u || (count != 0 && windows == 0)) return 0;
    for (i = 0; i < count; ++i) {
        w = &windows[i];
        if (!valid_rect(&w->bounds) || w->handle == 0 || w->handle > 4u ||
            w->rank == 0 || w->rank > 4u || (w->flags & 0xFCu) != 0 ||
            (unsigned int)(w->bounds.right - w->bounds.left) < 16u ||
            (unsigned int)(w->bounds.bottom - w->bounds.top) <= 17u) return 0;
        for (j = 0; j < i; ++j)
            if (windows[j].handle == w->handle || windows[j].rank == w->rank) return 0;
    }
    return 1;
}

uint8_t udeks_repaint_peek(struct udeks_repaint_job *job, uint16_t revision,
    const struct udeks_repaint_window *windows, uint8_t count,
    struct udeks_repaint_work *work)
{
    const struct udeks_repaint_window *w;
    struct udeks_repaint_rect bounds, clip;
    uint8_t i, selected, status = live(job);
    if (status != UDEKS_REPAINT_OK) return status;
    if (revision != job->revision) return UDEKS_REPAINT_STALE;
    if (work == 0 || !valid_scene(windows, count)) return UDEKS_REPAINT_INVALID;
    if (job->phase == 0) {
        if (!job->pending_valid) return UDEKS_REPAINT_IDLE;
        status = next_generation(job);
        if (status != UDEKS_REPAINT_OK) return status;
        job->current = job->pending;
        job->pending_valid = 0;
        job->phase = UDEKS_REPAINT_CLEAR;
        job->rank = job->handle = 0;
        job->cursor = job->current.top;
    }
    if (job->phase == UDEKS_REPAINT_CLEAR) {
        clip = job->current;
        clip.top = (uint8_t)job->cursor;
        clip.bottom = (uint8_t)(clip.top + UDEKS_REPAINT_CLEAR_ROWS);
        if (clip.bottom > job->current.bottom) clip.bottom = job->current.bottom;
    } else {
        if (job->phase == UDEKS_REPAINT_SELECT) {
            selected = count;
            for (i = 0; i < count; ++i) {
                w = &windows[i];
                if (w->rank > job->rank && (w->flags & UDEKS_REPAINT_VISIBLE) != 0 &&
                    (selected == count || w->rank < windows[selected].rank) &&
                    intersect(&clip, &job->current, &w->bounds)) selected = i;
            }
            job->cursor = 0;
            if (selected == count) {
                job->handle = 0;
                job->phase = UDEKS_REPAINT_COMMIT;
            } else {
                w = &windows[selected];
                job->rank = w->rank;
                job->handle = w->handle;
                job->phase = (w->flags & UDEKS_REPAINT_RETAINED) ?
                    UDEKS_REPAINT_RESTORE : UDEKS_REPAINT_CHROME;
            }
        }
        if (job->phase == UDEKS_REPAINT_COMMIT) clip = job->current;
        else {
            for (i = 0; i < count && windows[i].handle != job->handle; ++i) {}
            if (i == count) return UDEKS_REPAINT_STALE; /* Changed scene without invalidation. */
            bounds = windows[i].bounds;
            if (job->phase == UDEKS_REPAINT_CLIENT) {
                bounds.left += 3u;
                bounds.right -= 3u;
                bounds.top += 14u;
                bounds.bottom -= 3u;
                if (!intersect(&clip, &job->current, &bounds)) {
                    /* No client pixels in this damage. Select on the next poll. */
                    job->phase = UDEKS_REPAINT_SELECT;
                    job->handle = 0;
                    job->cursor = 0;
                    return UDEKS_REPAINT_YIELD;
                }
            } else if (!intersect(&clip, &job->current, &bounds))
                return UDEKS_REPAINT_STALE;
        }
    }
    work->clip = clip;
    work->ticket.generation = job->generation;
    work->ticket.revision = job->revision;
    work->ticket.cursor = job->cursor;
    work->ticket.phase = job->phase;
    work->ticket.rank = job->rank;
    work->ticket.handle = job->handle;
    return UDEKS_REPAINT_OK;
}

uint8_t udeks_repaint_validate(const struct udeks_repaint_job *job,
    uint16_t revision, const struct udeks_repaint_ticket *ticket)
{
    uint8_t status = live(job);
    if (status != UDEKS_REPAINT_OK) return status;
    if (ticket == 0) return UDEKS_REPAINT_INVALID;
    if (revision != job->revision || ticket->revision != job->revision ||
        ticket->generation != job->generation || ticket->cursor != job->cursor ||
        ticket->rank != job->rank || ticket->handle != job->handle ||
        ticket->phase != job->phase || job->phase == 0 || job->phase == UDEKS_REPAINT_SELECT)
        return UDEKS_REPAINT_STALE;
    return UDEKS_REPAINT_OK;
}

uint8_t udeks_repaint_ack(struct udeks_repaint_job *job, uint16_t revision,
    const struct udeks_repaint_ticket *ticket, uint8_t result)
{
    uint8_t status = udeks_repaint_validate(job, revision, ticket);
    if (status != UDEKS_REPAINT_OK) return status;
    if (result > UDEKS_REPAINT_MORE ||
        (job->phase == UDEKS_REPAINT_CLEAR && result != UDEKS_REPAINT_DONE))
        return UDEKS_REPAINT_INVALID;
    if (job->phase == UDEKS_REPAINT_CLEAR) {
        job->cursor += UDEKS_REPAINT_CLEAR_ROWS;
        if (job->cursor >= job->current.bottom) {
            job->phase = UDEKS_REPAINT_SELECT;
            job->cursor = 0;
        }
    } else if (result == UDEKS_REPAINT_MORE) {
        if (job->cursor == 0xFFFFu) {
            job->generation = 0;
            job->phase = UDEKS_REPAINT_FAILED;
            job->handle = 0;
            return UDEKS_REPAINT_EXHAUSTED;
        }
        ++job->cursor;
    } else {
        job->cursor = 0;
        if (job->phase == UDEKS_REPAINT_CHROME) job->phase = UDEKS_REPAINT_CLIENT;
        else {
            job->handle = 0;
            job->phase = job->phase == UDEKS_REPAINT_COMMIT ? 0 : UDEKS_REPAINT_SELECT;
        }
    }
    return UDEKS_REPAINT_OK;
}

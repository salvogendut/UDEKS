/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private bounded retained-image provider. No legacy composition or app call. */
#include "cache_restore.h"
#include "../window-repaint-admission/admission.h"
#include "udeks/window_cache_state.h"

static unsigned char leave(unsigned char result)
{
    if (repaint_admission_release(REPAINT_ADMISSION_CACHE) != 0)
        return REPAINT_RESTORE_UNRECOVERABLE;
    return result;
}

static unsigned char repair(const struct udeks_repaint_window *window)
{
    return repaint_restore_repair(window->handle, &window->bounds) == UDEKS_REPAINT_OK ?
        REPAINT_RESTORE_REPAIR_QUEUED : REPAINT_RESTORE_UNRECOVERABLE;
}

unsigned char repaint_restore_step(const struct udeks_repaint_lane_work *work,
                                  const struct udeks_repaint_window *window)
{
    unsigned char status, phase, row, final;
    const struct udeks_repaint_rect *clip, *bounds;

    if (!work || !window || work->ticket.phase != UDEKS_REPAINT_RESTORE)
        return UDEKS_REPAINT_INVALID;
    clip = &work->clip;
    bounds = &window->bounds;
    if (!(window->flags & UDEKS_REPAINT_VISIBLE) ||
        !(window->flags & UDEKS_REPAINT_RETAINED) ||
        window->handle == 0 || window->handle > 4u ||
        window->handle != (work->ticket.selector & 7u) ||
        window->rank != (work->ticket.selector >> 3) ||
        bounds->left >= bounds->right || bounds->right > 320u ||
        bounds->top >= bounds->bottom || bounds->bottom > 200u ||
        clip->left != bounds->left || clip->right != bounds->right ||
        clip->top != bounds->top || clip->bottom != bounds->bottom ||
        work->ticket.cursor >= bounds->bottom - bounds->top)
        return UDEKS_REPAINT_INVALID;
    status = repaint_admission_try(REPAINT_ADMISSION_CACHE);
    if (status == REPAINT_ADMISSION_DEFERRED) return REPAINT_RESTORE_DEFERRED;
    if (status != 0) return UDEKS_REPAINT_INVALID;
    status = repaint_restore_validate(&work->ticket);
    if (status != UDEKS_REPAINT_OK) return leave(status);
    status = repaint_restore_image_valid(window->handle);
    if (status == UDEKS_CACHE_BUSY) return leave(REPAINT_RESTORE_DEFERRED);
    if (status != UDEKS_CACHE_OK) return leave(repair(window));
    phase = repaint_restore_phase();
    if (phase == UDEKS_CACHE_READY && work->ticket.cursor == 0) {
        if (repaint_restore_begin_full(window->handle) != UDEKS_CACHE_OK)
            return leave(REPAINT_RESTORE_DEFERRED);
        phase = repaint_restore_phase();
    }
    if (phase != UDEKS_CACHE_PASTING ||
        repaint_restore_owner() != window->handle ||
        repaint_restore_row() != work->ticket.cursor)
        return leave(repair(window));
    row = (unsigned char)work->ticket.cursor;
    final = row + 1u == bounds->bottom - bounds->top;
    if (repaint_restore_step_row() != UDEKS_CACHE_OK ||
        repaint_restore_owner() != window->handle ||
        repaint_restore_row() != row + 1u ||
        repaint_restore_phase() != (final ? UDEKS_CACHE_READY : UDEKS_CACHE_PASTING))
        return leave(repair(window));
    if ((row & 7u) == 7u || final) repaint_restore_commit();
    status = repaint_restore_ack(&work->ticket,
        final ? UDEKS_REPAINT_DONE : UDEKS_REPAINT_MORE);
    if (status != UDEKS_REPAINT_OK) return leave(repair(window));
    return leave(UDEKS_REPAINT_OK);
}

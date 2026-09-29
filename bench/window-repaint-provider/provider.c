/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private bounded client dispatch prototype; never linked into the OS. */
#include "provider.h"

unsigned char repaint_client_step(const struct udeks_repaint_lane_work *work,
    const struct udeks_repaint_window *window)
{
    unsigned char status, row;
    const struct udeks_repaint_rect *clip, *bounds;

    if (!work || !window) return UDEKS_REPAINT_INVALID;
    if (work->ticket.phase != UDEKS_REPAINT_CLIENT) return UDEKS_REPAINT_INVALID;
    status = repaint_client_validate(&work->ticket);
    if (status != UDEKS_REPAINT_OK) return status;
    clip = &work->clip;
    bounds = &window->bounds;
    /* Caller resolves the live window under scene ownership; this cheap
     * identity check rejects a different/reused slot before any pixels. */
    if (!(window->flags & UDEKS_REPAINT_VISIBLE) ||
        window->handle != (work->ticket.selector & 7u) ||
        window->rank != (work->ticket.selector >> 3))
        return UDEKS_REPAINT_STALE;
    if (bounds->left >= bounds->right || bounds->right > 320u ||
        bounds->top >= bounds->bottom || bounds->bottom > 200u ||
        bounds->right - bounds->left <= 6u ||
        bounds->bottom - bounds->top <= 17u ||
        clip->left < bounds->left + 3u ||
        clip->right > bounds->right - 3u ||
        clip->top < bounds->top + 14u ||
        clip->bottom > bounds->bottom - 3u ||
        clip->left >= clip->right || clip->top >= clip->bottom ||
        work->ticket.cursor >= clip->bottom - clip->top)
        return UDEKS_REPAINT_INVALID;
    row = clip->top + (unsigned char)work->ticket.cursor;
    status = repaint_client_ready(window->handle, row);
    if (status == REPAINT_PROVIDER_DEFER) return status;
    if (status != UDEKS_REPAINT_OK) return UDEKS_REPAINT_INVALID;
    repaint_client_set_clip(clip->left, clip->top, clip->right - clip->left,
        clip->bottom - clip->top);
    repaint_client_draw_row(window->handle, row);
    repaint_client_reset_clip();
    return repaint_client_ack(&work->ticket,
        row + 1u < clip->bottom ? UDEKS_REPAINT_MORE : UDEKS_REPAINT_DONE);
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private host/compile-only scene-edit gate, not a public window API. */
#ifndef UDEKS_PRIVATE_REPAINT_EDIT_FENCE_H
#define UDEKS_PRIVATE_REPAINT_EDIT_FENCE_H
#include "udeks/repaint_lane.h"

#define REPAINT_EDIT_DEFERRED 8u /* distinct from backend-required and provider defer */

/* The caller MUST already own exclusive, NMI-safe scene/graphics admission
 * when available=1. A zero availability is a side-effect-free retry signal;
 * it must not be translated to public INVALID or silently discarded.
 * old/new are the pre- and proposed post-edit visible bounds. At least one
 * must exist. Call only before the scene/cache/content edit, and edit only
 * after OK. This wrapper does not acquire a lease or queue application data.
 */
unsigned char repaint_edit_fence(unsigned char available,
    const struct udeks_repaint_rect *old_bounds,
    const struct udeks_repaint_rect *new_bounds);
#endif

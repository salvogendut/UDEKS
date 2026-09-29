/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Size-only alternative: trusted manager geometry, separate from reference. */
#include "fence.h"

unsigned char repaint_edit_fence_trusted(unsigned char available,
    const struct udeks_repaint_rect *old_bounds,
    const struct udeks_repaint_rect *new_bounds)
{
    struct udeks_repaint_rect damage;
    if (!old_bounds && !new_bounds) return UDEKS_REPAINT_INVALID;
    if (!available) return REPAINT_EDIT_DEFERRED;
    if (old_bounds) damage = *old_bounds;
    else damage = *new_bounds;
    if (old_bounds && new_bounds) {
        if (new_bounds->left < damage.left) damage.left = new_bounds->left;
        if (new_bounds->right > damage.right) damage.right = new_bounds->right;
        if (new_bounds->top < damage.top) damage.top = new_bounds->top;
        if (new_bounds->bottom > damage.bottom) damage.bottom = new_bounds->bottom;
    }
    return udeks_lane_changed(&damage);
}

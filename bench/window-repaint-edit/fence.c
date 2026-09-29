/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "fence.h"

static unsigned char valid(const struct udeks_repaint_rect *r)
{
    return r != 0 && r->left < r->right && r->right <= 320u &&
        r->top < r->bottom && r->bottom <= 200u;
}

unsigned char repaint_edit_fence(unsigned char available,
    const struct udeks_repaint_rect *old_bounds,
    const struct udeks_repaint_rect *new_bounds)
{
    struct udeks_repaint_rect damage;

    if ((!old_bounds && !new_bounds) ||
        (old_bounds && !valid(old_bounds)) ||
        (new_bounds && !valid(new_bounds))) return UDEKS_REPAINT_INVALID;
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

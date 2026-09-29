/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private paired edit envelope. No OS image links this prototype. */
#include "admission.h"
#include "../window-repaint-edit/fence.h"

unsigned char repaint_edit_begin(const struct udeks_repaint_rect *old_bounds,
    const struct udeks_repaint_rect *new_bounds)
{
    unsigned char result = repaint_admission_try(REPAINT_ADMISSION_EDIT);
    if (result != 0) return result;
    result = repaint_edit_fence(1, old_bounds, new_bounds);
    if (result != UDEKS_REPAINT_OK) {
        /* Failure/defer never leaves an EDIT lease for a caller to forget. */
        repaint_admission_release(REPAINT_ADMISSION_EDIT);
    }
    return result;
}

unsigned char repaint_edit_end(void)
{
    return repaint_admission_release(REPAINT_ADMISSION_EDIT);
}

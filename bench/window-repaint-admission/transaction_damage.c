/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private size candidate: manager has already composed old/new into its
 * existing damage box. No second rectangle union is linked here. */
#include "admission.h"
#ifndef __CC65__
#define REPAINT_HOST
#endif
#include "../window-repaint-scenes/packet.h"
extern unsigned char repaint_control_damage(unsigned char op, unsigned char lease);

unsigned char repaint_edit_begin_damage(void)
{
    unsigned char result = repaint_admission_try(REPAINT_ADMISSION_EDIT);
    if (result != 0) return result;
    result = repaint_control_damage(REPAINT_CHANGED, 1u);
    if (result != 0) repaint_admission_release(REPAINT_ADMISSION_EDIT);
    return result;
}

unsigned char repaint_edit_end_damage(void)
{
    return repaint_admission_release(REPAINT_ADMISSION_EDIT);
}

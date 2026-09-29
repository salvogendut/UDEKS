/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "admission.h"

#pragma bss-name(push, "HIGHBSS")
unsigned char repaint_admission_owner;
#pragma bss-name(pop)

unsigned char repaint_admission_try(unsigned char owner)
{
    if (owner < REPAINT_ADMISSION_EDIT || owner > REPAINT_ADMISSION_CACHE)
        return REPAINT_ADMISSION_INVALID;
    if (repaint_admission_owner != REPAINT_ADMISSION_FREE)
        return REPAINT_ADMISSION_DEFERRED;
    repaint_admission_owner = owner;
    return 0;
}

unsigned char repaint_admission_release(unsigned char owner)
{
    if (owner < REPAINT_ADMISSION_EDIT || owner > REPAINT_ADMISSION_CACHE ||
        repaint_admission_owner != owner) return REPAINT_ADMISSION_INVALID;
    repaint_admission_owner = REPAINT_ADMISSION_FREE;
    return 0;
}
